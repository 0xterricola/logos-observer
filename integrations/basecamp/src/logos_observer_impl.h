#pragma once

#include <string>

#include <logos_module_context.h>

class LogosObserverImpl : public LogosModuleContext {
public:
    LogosObserverImpl();
    ~LogosObserverImpl();

    // Returns the module's current state.
    std::string getInfo();

protected:
    void onContextReady() override;
    LogosShutdown aboutToUnload() override;
};
