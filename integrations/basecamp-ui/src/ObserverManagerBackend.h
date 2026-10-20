#pragma once

#include <QObject>
#include <QString>

#include "rep_ObserverManagerBackend_source.h"

class LogosAPI;
struct LogosModules;

class ObserverManagerBackend
    : public ObserverManagerBackendSimpleSource
{
    Q_OBJECT

public:
    explicit ObserverManagerBackend(
        LogosAPI* api = nullptr,
        QObject* parent = nullptr);

    ~ObserverManagerBackend() override;

public slots:
    void checkHealth(
        QString endpoint,
        QString caCert,
        QString spkiPin) override;

    void checkChatHealth() override;

private:
    LogosAPI* m_api;
    LogosModules* m_modules;
};
