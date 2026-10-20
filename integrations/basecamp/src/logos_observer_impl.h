#pragma once

#include <string>

#include <logos_module_context.h>

class LogosObserverImpl : public LogosModuleContext {
public:
    LogosObserverImpl();
    ~LogosObserverImpl();

    // Returns the module's current state.
    std::string getInfo();

    // Read-only, TLS-verified Observer health probe.
    std::string getHealth(const std::string& configJson);

    // Read-only local Basecamp Chat diagnostics.
    std::string getChatHealth();

    // Read-only local Basecamp Chat diagnostics.

protected:
    void onContextReady() override;
    LogosShutdown aboutToUnload() override;
};
