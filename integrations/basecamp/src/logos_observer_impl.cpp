#include "logos_observer_impl.h"
#include "observer_health.h"
#include <nlohmann/json.hpp>
#include <cstdlib>

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

    if (!python || !*python || !runtime || !*runtime) {
        return serviceResultJson({
            false,
            "not_configured",
            "Observer runtime configuration is missing",
            0
        });
    }

    return serviceResultJson(
        managedService_.start(python, runtime)
    );
}

std::string LogosObserverImpl::getServiceStatus() {
    return serviceResultJson(managedService_.status());
}

std::string LogosObserverImpl::stopService() {
    return serviceResultJson(managedService_.stop());
}
