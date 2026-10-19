#include "observer_health.h"

#include <curl/curl.h>
#include <nlohmann/json.hpp>

#include <cctype>
#include <mutex>
#include <string>

using json = nlohmann::json;

namespace {

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
        url = config.at("url").get<std::string>();
        caCert = config.at("ca_cert").get<std::string>();
        pin = curlPin(
            config.at("spki_pin").get<std::string>()
        );
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
