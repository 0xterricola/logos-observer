#include "managed_observer_service.h"
#include "observer_network_config.h"

#include <cstdlib>
#include <filesystem>
#include <vector>

#ifndef _WIN32
#include <cerrno>
#include <csignal>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

namespace fs = std::filesystem;

ManagedObserverService::~ManagedObserverService() {
    stop();
}

bool ManagedObserverService::runningLocked() {
#ifndef _WIN32
    if (pid_ <= 0) return false;

    int childStatus = 0;
    pid_t result;
    do {
        result = waitpid(pid_, &childStatus, WNOHANG);
    } while (result < 0 && errno == EINTR);

    if (result == 0) return true;

    const int previousPid = pid_;
    pid_ = -1;

    if (result == previousPid) {
        if (WIFEXITED(childStatus)) {
            lastFailure_ = "Observer exited unexpectedly (code " +
                std::to_string(WEXITSTATUS(childStatus)) + ")";
        } else if (WIFSIGNALED(childStatus)) {
            lastFailure_ = "Observer terminated unexpectedly (signal " +
                std::to_string(WTERMSIG(childStatus)) + ")";
        }
    } else {
        lastFailure_ = "Unable to verify managed child process";
    }
#endif
    return false;
}

ManagedObserverResult ManagedObserverService::status() {
    std::lock_guard<std::mutex> lock(mutex_);

    if (runningLocked()) {
        return {true, "running", "Managed process is alive", pid_};
    }

    if (!lastFailure_.empty()) {
        return {false, "error", lastFailure_, 0};
    }
    return {true, "stopped", "No managed process", 0};
}

ManagedObserverResult ManagedObserverService::start(
    const std::string& executablePath,
    const std::string& runtimeDir
) {
    std::lock_guard<std::mutex> lock(mutex_);

#ifdef _WIN32
    return {false, "unsupported", "Windows launcher not implemented", 0};
#else
    if (runningLocked()) {
        return {false, "running", "Observer already started", pid_};
    }

    lastFailure_.clear();

    const fs::path executable(executablePath);
    const bool pythonMode = !runtimeDir.empty();

    if (!executable.is_absolute() ||
        !fs::is_regular_file(executable) ||
        access(executable.c_str(), X_OK) != 0) {
        return {
            false, "error",
            "Observer executable missing or not executable: " +
                executable.string(),
            0
        };
    }

    fs::path script;

    if (pythonMode) {
        script = fs::path(runtimeDir) / "v2_server.py";

        if (!script.is_absolute() || !fs::is_regular_file(script)) {
            return {
                false, "error",
                "Invalid absolute Observer runtime directory",
                0
            };
        }
    }

    const char* home = std::getenv("HOME");
    if (!home || !*home) {
        return {false, "error", "HOME is not configured", 0};
    }

    const fs::path stateDir =
        fs::path(home) / ".local/state/logos-observer/basecamp";

    std::error_code ec;
    fs::create_directories(stateDir, ec);
    if (ec || chmod(stateDir.c_str(), 0700) != 0) {
        return {false, "error", "Unable to create private state directory", 0};
    }

    const fs::path logPath = stateDir / "observer.log";
    const int logFd = open(
        logPath.c_str(), O_WRONLY | O_CREAT | O_APPEND, 0600
    );
    if (logFd < 0) {
        return {false, "error", "Unable to open Observer log", 0};
    }

    const auto network = observer_network::current();

    if (!network.valid) {
        return {
            false,
            "not_configured",
            "LOGOS_OBSERVER_LAN_IP must be a private IPv4 address",
            0
        };
    }

    std::vector<std::string> arguments = {
        executable.string()
    };

    if (pythonMode) {
        arguments.push_back(script.string());
    }

    arguments.insert(arguments.end(), {
        "--host", network.host,
        "--advertise-host", network.host,
        "--port", "18446",
        "--state-dir", stateDir.string(),
        "--chat-bridge", "http://127.0.0.1:8645/rpc"
    });

    std::vector<char*> argv;
    for (auto& argument : arguments) {
        argv.push_back(argument.data());
    }
    argv.push_back(nullptr);

    const pid_t child = fork();

    if (child == 0) {
        dup2(logFd, STDOUT_FILENO);
        dup2(logFd, STDERR_FILENO);
        if (logFd > STDERR_FILENO) close(logFd);

        execv(argv[0], argv.data());
        _exit(127);
    }

    close(logFd);

    if (child < 0) {
        return {false, "error", "Unable to fork Observer process", 0};
    }

    pid_ = static_cast<int>(child);

    // Detect immediate interpreter and startup failures.
    for (int attempt = 0; attempt < 10; ++attempt) {
        usleep(100000);
        if (!runningLocked()) {
            return {false, "error", lastFailure_, 0};
        }
    }

    return {true, "starting", "Observer process launched", pid_};
#endif
}

ManagedObserverResult ManagedObserverService::stop() {
    std::lock_guard<std::mutex> lock(mutex_);

#ifdef _WIN32
    return {false, "unsupported", "Windows launcher not implemented", 0};
#else
    if (!runningLocked()) {
        return {true, "stopped", "Observer already stopped", 0};
    }

    if (kill(pid_, SIGTERM) != 0 && errno != ESRCH) {
        return {false, "error", "Unable to signal managed process", pid_};
    }

    // Give the server time to close cleanly and flush state.
    for (int attempt = 0; attempt < 50; ++attempt) {
        if (!runningLocked()) {
            lastFailure_.clear();
        return {true, "stopped", "Observer stopped gracefully", 0};
        }
        usleep(100000);
    }

    // Only signal a process still confirmed as our child.
    if (runningLocked()) {
        kill(pid_, SIGKILL);

        int childStatus = 0;
        while (waitpid(pid_, &childStatus, 0) < 0 && errno == EINTR) {
        }
        pid_ = -1;
    }

    lastFailure_.clear();
    return {true, "stopped", "Observer stopped after timeout", 0};
#endif
}
