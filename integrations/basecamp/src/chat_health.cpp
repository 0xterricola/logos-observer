#include <curl/curl.h>
#include <nlohmann/json.hpp>

#include <mutex>
#include <string>

using json = nlohmann::json;

namespace {

constexpr char BRIDGE_URL[] = "http://127.0.0.1:8645/rpc";
constexpr size_t MAX_RESPONSE_BYTES = 1024 * 1024;

struct RpcReply {
    bool connected = false;
    bool valid = false;
    bool timedOut = false;
    json response;
};

std::string diagnostic(
    bool bridge,
    bool chat,
    bool readable,
    json count,
    const char* reason
) {
    return json{
        {"chat_bridge", {{"reachable", bridge}}},
        {"basecamp_chat", {{"available", chat}}},
        {"conversations", {
            {"readable", readable},
            {"count", count}
        }},
        {"reason", reason}
    }.dump();
}

size_t receiveBody(
    char* data, size_t size, size_t count, void* userdata
) {
    auto* body = static_cast<std::string*>(userdata);

    if (size && count > MAX_RESPONSE_BYTES / size)
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

RpcReply callRpc(const char* method, int id) {
    RpcReply reply;

    if (!initCurl())
        return reply;

    CURL* curl = curl_easy_init();
    if (!curl)
        return reply;

    const std::string payload = json{
        {"jsonrpc", "2.0"},
        {"id", id},
        {"method", method}
    }.dump();

    std::string body;

    curl_slist* headers = curl_slist_append(
        nullptr, "Content-Type: application/json");

    if (!headers) {
        curl_easy_cleanup(curl);
        return reply;
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
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &httpStatus);

    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);

    reply.timedOut = code == CURLE_OPERATION_TIMEDOUT;
    reply.connected = code == CURLE_OK;

    if (code != CURLE_OK || httpStatus != 200)
        return reply;

    try {
        json response = json::parse(body);

        if (!response.is_object() ||
            response.value("jsonrpc", std::string{}) != "2.0" ||
            !response.contains("id") ||
            !response["id"].is_number_integer() ||
            response["id"].get<int>() != id ||
            (!response.contains("result") &&
             !response.contains("error")))
            return reply;

        reply.valid = true;
        reply.response = std::move(response);
    } catch (...) {
        // Invalid JSON-RPC response.
    }

    return reply;
}

} // namespace

std::string probeChatHealth() {
    // Probe JSON-RPC independently of Chat initialization.
    const auto bridge = callRpc(
        "__observer_probe_nonexistent__", 99);

    if (!bridge.valid)
        return diagnostic(
            false, false, false, nullptr,
            bridge.timedOut ? "bridge_timeout" :
            bridge.connected ? "invalid_bridge_response" :
                               "bridge_unreachable");

    const auto address = callRpc("chat_module.get_address", 1);

    if (!address.valid)
        return diagnostic(
            true, false, false, nullptr,
            address.timedOut ? "chat_rpc_timeout" :
                               "chat_rpc_unavailable");

    if (address.response.contains("error"))
        return diagnostic(
            true, false, false, nullptr, "chat_rpc_error");

    if (!address.response.contains("result") ||
        !address.response["result"].is_string())
        return diagnostic(
            true, false, false, nullptr, "invalid_chat_response");

    if (address.response["result"].get<std::string>().empty())
        return diagnostic(
            true, false, false, nullptr, "chat_not_started");

    const auto conversations =
        callRpc("chat_module.list_conversations", 2);

    if (!conversations.valid)
        return diagnostic(
            true, true, false, nullptr,
            conversations.timedOut ? "conversations_timeout" :
                                     "conversations_unavailable");

    if (conversations.response.contains("error"))
        return diagnostic(
            true, true, false, nullptr, "conversations_rpc_error");

    if (!conversations.response.contains("result") ||
        !conversations.response["result"].is_array())
        return diagnostic(
            true, true, false, nullptr,
            "invalid_conversations_response");

    return diagnostic(
        true, true, true,
        conversations.response["result"].size(),
        "conversations_readable");
}
