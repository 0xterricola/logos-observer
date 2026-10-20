#include "logos_observer_impl.h"
#include "observer_health.h"

LogosObserverImpl::LogosObserverImpl() = default;

LogosObserverImpl::~LogosObserverImpl() = default;

std::string LogosObserverImpl::getInfo() {
    return R"json({
        "module": "logos_observer",
        "version": "0.1.2",
        "managed_service": "not_configured"
    })json";
}

void LogosObserverImpl::onContextReady() {
    // Service management will be implemented in a later milestone.
    // Do not automatically start another Observer instance.
}

LogosShutdown LogosObserverImpl::aboutToUnload() {
    // No managed processes or resources to release yet.
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
