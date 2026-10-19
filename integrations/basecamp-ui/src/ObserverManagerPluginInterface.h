#pragma once

#include <QtPlugin>
#include "interface.h"

class ObserverManagerPluginInterface : public PluginInterface
{
public:
    virtual ~ObserverManagerPluginInterface() = default;
};

#define ObserverManagerPluginInterface_iid \
    "org.logos.ObserverManagerPluginInterface"

Q_DECLARE_INTERFACE(
    ObserverManagerPluginInterface,
    ObserverManagerPluginInterface_iid)
