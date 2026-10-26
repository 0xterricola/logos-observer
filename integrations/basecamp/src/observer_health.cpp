#include "observer_health.h"
#include "observer_network_config.h"

#include <openssl/pem.h>
#include <openssl/sha.h>
#include <openssl/evp.h>
#include <openssl/x509.h>

#include <filesystem>
#include <vector>
#include <cstdlib>

#include <curl/curl.h>
#include <nlohmann/json.hpp>

#include <cctype>
#include <mutex>
#include <string>

using json = nlohmann::json;

namespace {

std::string observerPinFromCertificate(const std::string& path)
{
    BIO* bio = BIO_new_file(path.c_str(), "rb");
    if (!bio)
        return {};

    X509* cert = PEM_read_bio_X509(bio, nullptr, nullptr, nullptr);
    BIO_free(bio);

    if (!cert)
        return {};

    EVP_PKEY* key = X509_get_pubkey(cert);
    X509_free(cert);

    if (!key)
        return {};

    const int length = i2d_PUBKEY(key, nullptr);
    if (length <= 0) {
        EVP_PKEY_free(key);
        return {};
    }

    std::vector<unsigned char> der(
        static_cast<size_t>(length));

    unsigned char* cursor = der.data();
    const int written = i2d_PUBKEY(key, &cursor);
    EVP_PKEY_free(key);

    if (written != length)
        return {};

    unsigned char digest[SHA256_DIGEST_LENGTH];

    if (!SHA256(der.data(), der.size(), digest))
        return {};

    unsigned char encoded[
        4 * ((SHA256_DIGEST_LENGTH + 2) / 3) + 1
    ] = {};

    if (EVP_EncodeBlock(
            encoded, digest, SHA256_DIGEST_LENGTH) <= 0)
        return {};

    std::string value(
        reinterpret_cast<const char*>(encoded));

    for (char& character : value) {
        if (character == '+') character = '-';
        else if (character == '/') character = '_';
    }

    while (!value.empty() && value.back() == '=')
        value.pop_back();

    return "sha256/" + value;
}


constexpr size_t MAX_RESPONSE_BYTES = 4096;

std::string failure(const std::string& reason) {
    return json{
        {"observer", {
            {"reachable", false},
            {"identity_verified", false},
            {"healthy", false}
        }},
        {"error", reason}
    }.dump();
}

size_t receiveBody(
    char* data,
    size_t size,
    size_t count,
    void* userdata
) {
    auto* body = static_cast<std::string*>(userdata);
    const size_t bytes = size * count;

    if (bytes > MAX_RESPONSE_BYTES ||
        body->size() > MAX_RESPONSE_BYTES - bytes) {
        return 0;
    }

    body->append(data, bytes);
    return bytes;
}

// Observer: sha256/<unpadded base64url>
// libcurl:  sha256//<padded standard base64>
std::string curlPin(const std::string& observerPin) {
    const std::string prefix = "sha256/";

    if (observerPin.rfind(prefix, 0) != 0) {
        return {};
    }

    std::string encoded = observerPin.substr(prefix.size());

    // SHA-256 produces 32 bytes: 43 unpadded Base64URL characters.
    if (encoded.size() != 43) {
        return {};
    }

    for (char& c : encoded) {
        const unsigned char uc = static_cast<unsigned char>(c);

        if (c == '-') {
            c = '+';
        } else if (c == '_') {
            c = '/';
        } else if (!std::isalnum(uc)) {
            return {};
        }
    }

    encoded += "=";
    return "sha256//" + encoded;
}

bool validHealthUrl(const std::string& url) {
    return url.rfind("https://", 0) == 0 &&
           url.size() > 15 &&
           url.compare(url.size() - 7, 7, "/health") == 0 &&
           url.find('@') == std::string::npos &&
           url.find('?') == std::string::npos &&
           url.find('#') == std::string::npos;
}

bool initCurl() {
    static std::once_flag once;
    static bool initialized = false;

    std::call_once(once, [] {
        initialized =
            curl_global_init(CURL_GLOBAL_DEFAULT) == CURLE_OK;
    });

    return initialized;
}

} // namespace

std::string probeObserverHealth(const std::string& configJson) {
    json config;

    try {
        config = json::parse(configJson);

        if (!config.is_object()) {
            return failure("invalid_config");
        }
    } catch (...) {
        return failure("invalid_config");
    }

    std::string url;
    std::string caCert;
    std::string pin;

    try {
        if (config.contains("managed")) {
            if (config.size() != 1 ||
                config.at("managed") != true) {
                return failure("invalid_config");
            }

            const auto network = observer_network::current();

            if (!network.valid)
                return failure("invalid_managed_network");

            const char* home = std::getenv("HOME");

            if (!home || !*home)
                return failure("missing_home");

            const auto certPath =
                std::filesystem::path(home) /
                ".local/state/logos-observer/basecamp/"
                "observer-v2-cert.pem";

            const std::string observerPin =
                observerPinFromCertificate(certPath.string());

            if (observerPin.empty())
                return failure("managed_certificate_unavailable");

            url = "https://" + network.host + ":18446/health";
            caCert = certPath.string();
            pin = curlPin(observerPin);
        } else {
            url = config.at("url").get<std::string>();
            caCert = config.at("ca_cert").get<std::string>();
            pin = curlPin(
                config.at("spki_pin").get<std::string>()
            );
        }
    } catch (...) {
        return failure("missing_or_invalid_configuration");
    }

    if (!validHealthUrl(url) ||
        caCert.empty() ||
        caCert.front() != '/' ||
        pin.empty()) {
        return failure("invalid_endpoint_or_identity");
    }

    if (!initCurl()) {
        return failure("curl_initialization_failed");
    }

    CURL* curl = curl_easy_init();

    if (!curl) {
        return failure("curl_initialization_failed");
    }

    std::string body;

    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_CAINFO, caCert.c_str());
    curl_easy_setopt(curl, CURLOPT_PINNEDPUBLICKEY, pin.c_str());

    // Both certificate-chain and hostname validation are mandatory.
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 1L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 2L);

    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 0L);
    curl_easy_setopt(curl, CURLOPT_NOSIGNAL, 1L);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT_MS, 1500L);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, 3000L);

    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, receiveBody);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &body);

    const CURLcode result = curl_easy_perform(curl);

    long httpStatus = 0;
    curl_easy_getinfo(
        curl,
        CURLINFO_RESPONSE_CODE,
        &httpStatus
    );

    curl_easy_cleanup(curl);

    if (result != CURLE_OK) {
        return failure(curl_easy_strerror(result));
    }

    bool healthy = false;

    try {
        const json response = json::parse(body);

        healthy =
            httpStatus == 200 &&
            response.is_object() &&
            response.value("ok", false) == true &&
            response.value("service", std::string{}) ==
                "logos-observer" &&
            response.value("protocol", std::string{}) ==
                "logos-observer-v2";
    } catch (...) {
        return failure("invalid_health_response");
    }

    return json{
        {"observer", {
            {"reachable", true},
            {"identity_verified", true},
            {"healthy", healthy}
        }},
        {"http_status", httpStatus},
        {"protocol", "logos-observer-v2"},
        {"ownership", "unmanaged"}
    }.dump();
}
