#include "logos_observer_impl.h"
#include "observer_health.h"
#include <nlohmann/json.hpp>
#include <cstdlib>

#if defined(__APPLE__) || (defined(__linux__) && defined(__x86_64__))
#include <dlfcn.h>
#include <filesystem>
#endif

LogosObserverImpl::LogosObserverImpl() = default;

LogosObserverImpl::~LogosObserverImpl() = default;

std::string LogosObserverImpl::getInfo() {
    return R"json({
        "module": "logos_observer",
        "version": "0.1.4",
        "managed_service": "manual"
    })json";
}

void LogosObserverImpl::onContextReady() {
    // Service management will be implemented in a later milestone.
    // Do not automatically start another Observer instance.
}

LogosShutdown LogosObserverImpl::aboutToUnload() {
    managedService_.stop();
    return LogosShutdown::Synchronous;
}


std::string LogosObserverImpl::getHealth(
    const std::string& configJson
) {
    return probeObserverHealth(configJson);
}


// Implemented in chat_health.cpp.
std::string probeChatHealth();

std::string LogosObserverImpl::getChatHealth() {
    return probeChatHealth();
}


namespace {
#if defined(__APPLE__) || (defined(__linux__) && defined(__x86_64__))
int modulePathAnchor = 0;

std::string bundledObserverPath() {
    Dl_info info{};

    if (dladdr(&modulePathAnchor, &info) == 0 ||
        !info.dli_fname || !*info.dli_fname) {
        return {};
    }

    const std::filesystem::path modulePath(info.dli_fname);

    if (!modulePath.is_absolute()) {
        return {};
    }

#if defined(__APPLE__)
    constexpr const char* runtimeRelative =
        "assets/lidl/observer-runtime/portable-macos-arm64/logos-observer";
#else
    constexpr const char* runtimeRelative =
        "assets/lidl/observer-runtime/portable-linux-x86_64/logos-observer";
#endif

    return (modulePath.parent_path() / runtimeRelative).string();
}
#endif

std::string serviceResultJson(const ManagedObserverResult& result) {
    return nlohmann::json{
        {"ok", result.ok},
        {"state", result.state},
        {"detail", result.detail},
        {"pid", result.pid}
    }.dump();
}
}

std::string LogosObserverImpl::startService() {
    const char* python = std::getenv("LOGOS_OBSERVER_PYTHON");
    const char* runtime = std::getenv("LOGOS_OBSERVER_RUNTIME_DIR");

    const bool hasPython = python && *python;
    const bool hasRuntime = runtime && *runtime;

    // Preserve explicit development configuration.
    if (hasPython || hasRuntime) {
        if (!hasPython || !hasRuntime) {
            return serviceResultJson({
                false,
                "not_configured",
                "Both Observer development overrides are required",
                0
            });
        }

        return serviceResultJson(
            managedService_.start(python, runtime)
        );
    }

#if defined(__APPLE__) || (defined(__linux__) && defined(__x86_64__))
    const std::string executable = bundledObserverPath();

    if (executable.empty()) {
        return serviceResultJson({
            false,
            "not_configured",
            "Unable to locate installed Observer module",
            0
        });
    }

    return serviceResultJson(
        managedService_.start(executable, "")
    );
#else
    return serviceResultJson({
        false,
        "unsupported",
        "Bundled Observer runtime is not available on this platform",
        0
    });
#endif
}

std::string LogosObserverImpl::getServiceStatus() {
    return serviceResultJson(managedService_.status());
}

std::string LogosObserverImpl::stopService() {
    return serviceResultJson(managedService_.stop());
}
