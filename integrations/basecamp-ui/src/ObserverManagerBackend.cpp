#include "ObserverManagerBackend.h"

#include <logos_sdk.h>

#include <QJsonDocument>
#include <QJsonObject>
#include <QMetaObject>
#include <QPointer>

ObserverManagerBackend::ObserverManagerBackend(
    LogosAPI* api,
    QObject* parent)
    : ObserverManagerBackendSimpleSource(parent),
      m_api(api ? api : new LogosAPI("logos_observer_ui", this)),
      m_modules(new LogosModules(m_api))
{
    setReady(true);
    setServiceBusy(false);
    setServiceStatus(QStringLiteral("Not checked"));
    setServiceDetails(QStringLiteral(
        "Managed Observer status has not been checked."));

    setHealthBusy(false);
    setChatBusy(false);
    setChatBridgeStatus(QStringLiteral("Not checked"));
    setChatStatus(QStringLiteral("Not checked"));
    setConversationsStatus(QStringLiteral("Not checked"));
    setChatDetails(QString());
    setHealthStatus(QStringLiteral("Not checked"));
    setHealthDetails(QStringLiteral(
        "Configure the Observer connection and check its health."));
}

ObserverManagerBackend::~ObserverManagerBackend()
{
    delete m_modules;
}

void ObserverManagerBackend::checkHealth(
    QString endpoint,
    QString caCert,
    QString spkiPin)
{
    if (healthBusy())
        return;

    endpoint = endpoint.trimmed();
    caCert = caCert.trimmed();
    spkiPin = spkiPin.trimmed();

    if (endpoint.isEmpty() ||
        caCert.isEmpty() ||
        spkiPin.isEmpty()) {
        setHealthStatus(QStringLiteral("Configuration required"));
        setHealthDetails(QStringLiteral(
            "Provide the HTTPS endpoint, trusted certificate, "
            "and Observer SPKI pin."));
        return;
    }

    QJsonObject config{
        {"url", endpoint},
        {"ca_cert", caCert},
        {"spki_pin", spkiPin}
    };

    const QString configJson = QString::fromUtf8(
        QJsonDocument(config).toJson(QJsonDocument::Compact));

    setHealthBusy(true);
    setHealthStatus(QStringLiteral("Checking..."));
    setHealthDetails(QString());

    QPointer<ObserverManagerBackend> guard(this);

    m_modules->logos_observer.getHealthAsyncResult(
        configJson,
        [guard](logos::AsyncResult<QString> outcome) {
            const bool succeeded = outcome.ok();
            const QString result = outcome.value;

            if (!guard)
                return;

            QMetaObject::invokeMethod(
                guard.data(),
                [guard, succeeded, result]() {
                    if (!guard)
                        return;

                    guard->setHealthBusy(false);

                    if (!succeeded) {
                        guard->setHealthStatus(
                            QStringLiteral("Module call failed"));
                        guard->setHealthDetails(
                            QStringLiteral(
                                "Could not retrieve Observer health."));
                        return;
                    }

                    QJsonParseError error;
                    const QJsonDocument document =
                        QJsonDocument::fromJson(
                            result.toUtf8(), &error);

                    if (error.error != QJsonParseError::NoError ||
                        !document.isObject()) {
                        guard->setHealthStatus(
                            QStringLiteral("Invalid response"));
                        guard->setHealthDetails(result);
                        return;
                    }

                    const QJsonObject response = document.object();
                    const QJsonObject observer =
                        response.value("observer").toObject();

                    const bool healthy =
                        observer.value("healthy").toBool() &&
                        observer.value("identity_verified").toBool();

                    guard->setHealthStatus(
                        healthy
                            ? QStringLiteral("Healthy")
                            : QStringLiteral("Unavailable or unhealthy"));

                    guard->setHealthDetails(
                        QString::fromUtf8(
                            document.toJson(QJsonDocument::Indented)));
                },
                Qt::QueuedConnection);
        });
}


void ObserverManagerBackend::checkChatHealth()
{
    if (chatBusy())
        return;

    setChatBusy(true);
    setChatBridgeStatus(QStringLiteral("Checking..."));
    setChatStatus(QStringLiteral("Checking..."));
    setConversationsStatus(QStringLiteral("Checking..."));
    setChatDetails(QString());

    QPointer<ObserverManagerBackend> guard(this);

    m_modules->logos_observer.getChatHealthAsyncResult(
        [guard](logos::AsyncResult<QString> outcome) {
            const bool succeeded = outcome.ok();
            const QString result = outcome.value;

            if (!guard)
                return;

            QMetaObject::invokeMethod(
                guard.data(),
                [guard, succeeded, result]() {
                    if (!guard)
                        return;

                    guard->setChatBusy(false);

                    if (!succeeded) {
                        guard->setChatBridgeStatus(
                            QStringLiteral("Unknown"));
                        guard->setChatStatus(
                            QStringLiteral("Unknown"));
                        guard->setConversationsStatus(
                            QStringLiteral("Unknown"));
                        guard->setChatDetails(
                            QStringLiteral("Module call failed."));
                        return;
                    }

                    QJsonParseError error;
                    const QJsonDocument document =
                        QJsonDocument::fromJson(
                            result.toUtf8(), &error);

                    if (error.error != QJsonParseError::NoError ||
                        !document.isObject()) {
                        guard->setChatBridgeStatus(
                            QStringLiteral("Unknown"));
                        guard->setChatStatus(
                            QStringLiteral("Unknown"));
                        guard->setConversationsStatus(
                            QStringLiteral("Unknown"));
                        guard->setChatDetails(
                            QStringLiteral("Invalid diagnostic response."));
                        return;
                    }

                    const QJsonObject response = document.object();
                    const bool bridge =
                        response.value("chat_bridge")
                            .toObject().value("reachable").toBool();
                    const bool chat =
                        response.value("basecamp_chat")
                            .toObject().value("available").toBool();

                    guard->setChatBridgeStatus(
                        bridge ? QStringLiteral("Responding")
                               : QStringLiteral("Unavailable"));

                    guard->setChatStatus(
                        chat ? QStringLiteral("Available")
                             : QStringLiteral("Unavailable"));

                    const QString reason =
                        response.value("reason").toString();

                    const QJsonObject conversations =
                        response.value("conversations").toObject();

                    const bool readable =
                        conversations.value("readable").toBool();

                    const int count =
                        conversations.value("count").toInt(-1);

                    if (!bridge) {
                        guard->setChatBridgeStatus(
                            reason == QStringLiteral("bridge_timeout")
                            ? QStringLiteral("Timed out")
                            : QStringLiteral("Unavailable"));
                        guard->setChatStatus(QStringLiteral("Unknown"));
                    } else if (!chat) {
                        guard->setChatStatus(
                            reason == QStringLiteral("chat_not_started")
                            ? QStringLiteral("Not started")
                            : reason == QStringLiteral("chat_rpc_timeout")
                            ? QStringLiteral("Timed out")
                            : QStringLiteral("Unknown"));
                    }

                    if (chat && readable && count >= 0) {
                        guard->setConversationsStatus(
                            QStringLiteral("Readable (%1)").arg(count));
                    } else if (!chat) {
                        guard->setConversationsStatus(
                            QStringLiteral("Not tested"));
                    } else {
                        guard->setConversationsStatus(
                            reason == QStringLiteral("conversations_timeout")
                            ? QStringLiteral("Timed out")
                            : QStringLiteral("Unavailable"));
                    }

                    guard->setChatDetails(reason);
                },
                Qt::QueuedConnection);
        });
}


void ObserverManagerBackend::applyServiceResult(
    bool succeeded,
    const QString& payload)
{
    setServiceBusy(false);

    if (!succeeded) {
        setServiceStatus(QStringLiteral("Module call failed"));
        setServiceDetails(QStringLiteral(
            "Could not communicate with the native Observer module."));
        return;
    }

    QJsonParseError error;
    const QJsonDocument document =
        QJsonDocument::fromJson(payload.toUtf8(), &error);

    if (error.error != QJsonParseError::NoError ||
        !document.isObject()) {
        setServiceStatus(QStringLiteral("Invalid response"));
        setServiceDetails(payload);
        return;
    }

    const QJsonObject response = document.object();
    const QString state = response.value("state").toString();

    setServiceStatus(
        state.isEmpty() ? QStringLiteral("Unknown") : state);

    setServiceDetails(response.value("detail").toString());
}


void ObserverManagerBackend::refreshServiceStatus()
{
    if (serviceBusy())
        return;

    setServiceBusy(true);
    setServiceStatus(QStringLiteral("Checking..."));
    setServiceDetails(QString());

    QPointer<ObserverManagerBackend> guard(this);

    m_modules->logos_observer.getServiceStatusAsyncResult(
        [guard](logos::AsyncResult<QString> outcome) {
            const bool succeeded = outcome.ok();
            const QString payload = outcome.value;

            if (!guard)
                return;

            QMetaObject::invokeMethod(
                guard.data(),
                [guard, succeeded, payload]() {
                    if (guard)
                        guard->applyServiceResult(
                            succeeded, payload);
                },
                Qt::QueuedConnection);
        });
}


void ObserverManagerBackend::startService()
{
    if (serviceBusy())
        return;

    setServiceBusy(true);
    setServiceStatus(QStringLiteral("Starting..."));
    setServiceDetails(QString());

    QPointer<ObserverManagerBackend> guard(this);

    m_modules->logos_observer.startServiceAsyncResult(
        [guard](logos::AsyncResult<QString> outcome) {
            const bool succeeded = outcome.ok();
            const QString payload = outcome.value;

            if (!guard)
                return;

            QMetaObject::invokeMethod(
                guard.data(),
                [guard, succeeded, payload]() {
                    if (guard)
                        guard->applyServiceResult(
                            succeeded, payload);
                },
                Qt::QueuedConnection);
        });
}


void ObserverManagerBackend::stopService()
{
    if (serviceBusy())
        return;

    setServiceBusy(true);
    setServiceStatus(QStringLiteral("Stopping..."));
    setServiceDetails(QString());

    QPointer<ObserverManagerBackend> guard(this);

    m_modules->logos_observer.stopServiceAsyncResult(
        [guard](logos::AsyncResult<QString> outcome) {
            const bool succeeded = outcome.ok();
            const QString payload = outcome.value;

            if (!guard)
                return;

            QMetaObject::invokeMethod(
                guard.data(),
                [guard, succeeded, payload]() {
                    if (guard)
                        guard->applyServiceResult(
                            succeeded, payload);
                },
                Qt::QueuedConnection);
        });
}
