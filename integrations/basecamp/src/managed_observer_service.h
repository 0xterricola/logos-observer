#pragma once

#include <mutex>
#include <string>

struct ManagedObserverResult {
    bool ok;
    std::string state;
    std::string detail;
    int pid;
};

class ManagedObserverService {
public:
    ~ManagedObserverService();

    ManagedObserverResult start(
        const std::string& pythonPath,
        const std::string& runtimeDir
    );

    ManagedObserverResult status();
    ManagedObserverResult stop();

private:
    bool runningLocked();

    std::mutex mutex_;
    int pid_ = -1;
    std::string lastFailure_;
};
