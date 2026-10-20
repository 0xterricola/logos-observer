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
    setHealthBusy(false);
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
