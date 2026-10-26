#pragma once

#include <arpa/inet.h>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>

namespace observer_network {

struct Config {
    std::string host;
    bool valid;
};

inline Config current()
{
    std::string host;

    const char* configured =
        std::getenv("LOGOS_OBSERVER_LAN_IP");

    if (configured && *configured) {
        host = configured;
    } else {
        const char* home = std::getenv("HOME");

        if (home && *home) {
            const auto path =
                std::filesystem::path(home) /
                ".local/state/logos-observer/basecamp/lan-ip";

            std::error_code ec;
            const bool exists = std::filesystem::exists(path, ec);

            if (ec)
                return {"", false};

            if (exists) {
                std::ifstream input(path);

                if (!input || !std::getline(input, host))
                    return {"", false};

                std::string extra;
                if (std::getline(input, extra))
                    return {"", false};
            }
        }
    }

    // Secure default: localhost.
    if (host.empty())
        return {"127.0.0.1", true};

    in_addr address{};

    if (inet_pton(AF_INET, host.c_str(), &address) != 1)
        return {"", false};

    const uint32_t ip = ntohl(address.s_addr);

    const bool privateAddress =
        (ip & 0xff000000u) == 0x0a000000u ||
        (ip & 0xfff00000u) == 0xac100000u ||
        (ip & 0xffff0000u) == 0xc0a80000u;

    if (!privateAddress)
        return {"", false};

    return {host, true};
}

}
