#include "ObserverManagerPlugin.h"
#include "ObserverManagerBackend.h"

#include <QDebug>

ObserverManagerPlugin::ObserverManagerPlugin(QObject* parent)
    : QObject(parent)
{
}

ObserverManagerPlugin::~ObserverManagerPlugin() = default;

void ObserverManagerPlugin::initLogos(LogosAPI* api)
{
    if (m_backend)
        return;

    m_backend = new ObserverManagerBackend(api, this);

    setBackend(m_backend);

    qDebug() << "ObserverManager: backend initialized";
}
