#include <curl/curl.h>
#include <nlohmann/json.hpp>

#include <mutex>
#include <string>

using json = nlohmann::json;

namespace {

constexpr char BRIDGE_URL[] = "http://127.0.0.1:8645/rpc";
constexpr size_t MAX_RESPONSE_BYTES = 4096;

std::string diagnostic(
    bool bridgeReachable,
    bool chatAvailable,
    const char* reason
) {
    return json{
        {"chat_bridge", {{"reachable", bridgeReachable}}},
        {"basecamp_chat", {{"available", chatAvailable}}},
        {"reason", reason}
    }.dump();
}

size_t receiveBody(
    char* data, size_t size, size_t count, void* userdata
) {
    auto* body = static_cast<std::string*>(userdata);

    if (size != 0 && count > MAX_RESPONSE_BYTES / size)
        return 0;

    const size_t bytes = size * count;

    if (bytes > MAX_RESPONSE_BYTES - body->size())
        return 0;

    body->append(data, bytes);
    return bytes;
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

std::string probeChatHealth() {
    if (!initCurl())
        return diagnostic(false, false, "curl_init_failed");

    CURL* curl = curl_easy_init();
    if (!curl)
        return diagnostic(false, false, "curl_init_failed");

    const std::string payload = json{
        {"jsonrpc", "2.0"},
        {"id", 1},
        {"method", "chat_module.get_address"}
    }.dump();

    std::string body;

    curl_slist* headers = curl_slist_append(
        nullptr, "Content-Type: application/json");

    if (!headers) {
        curl_easy_cleanup(curl);
        return diagnostic(false, false, "curl_init_failed");
    }

    curl_easy_setopt(curl, CURLOPT_URL, BRIDGE_URL);
    curl_easy_setopt(curl, CURLOPT_POST, 1L);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, payload.c_str());
    curl_easy_setopt(
        curl, CURLOPT_POSTFIELDSIZE, static_cast<long>(payload.size()));
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_PROXY, "");
    curl_easy_setopt(curl, CURLOPT_NOPROXY, "*");
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 0L);
    curl_easy_setopt(curl, CURLOPT_NOSIGNAL, 1L);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT_MS, 1000L);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, 3000L);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, receiveBody);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &body);

    const CURLcode code = curl_easy_perform(curl);

    long httpStatus = 0;
    curl_easy_getinfo(
        curl, CURLINFO_RESPONSE_CODE, &httpStatus);

    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);

    if (code != CURLE_OK)
        return diagnostic(false, false, "bridge_unreachable");

    try {
        const json response = json::parse(body);

        if (httpStatus != 200 ||
            !response.is_object() ||
            response.value("jsonrpc", std::string{}) != "2.0" ||
            !response.contains("id") ||
            !response["id"].is_number_integer() ||
            response["id"].get<int>() != 1) {
            return diagnostic(
                false, false, "invalid_bridge_response");
        }

        if (response.contains("error"))
            return diagnostic(
                true, false, "chat_rpc_error");

        if (!response.contains("result") ||
            !response["result"].is_string()) {
            return diagnostic(
                true, false, "invalid_chat_response");
        }

        const bool available =
            !response["result"].get<std::string>().empty();

        return diagnostic(
            true,
            available,
            available ? "chat_started" : "chat_not_started");

    } catch (...) {
        return diagnostic(
            false, false, "invalid_bridge_response");
    }
}
