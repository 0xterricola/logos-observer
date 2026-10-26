cmake_minimum_required(VERSION 3.14)
project(LogosObserverModule LANGUAGES CXX)

if(DEFINED ENV{LOGOS_MODULE_BUILDER_ROOT})
    include($ENV{LOGOS_MODULE_BUILDER_ROOT}/cmake/LogosModule.cmake)
elseif(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/cmake/LogosModule.cmake")
    include(cmake/LogosModule.cmake)
else()
    message(FATAL_ERROR "LogosModule.cmake not found")
endif()

logos_module(
    NAME logos_observer
    SOURCES
        src/logos_observer_impl.h
        src/logos_observer_impl.cpp
        src/managed_observer_service.h
        src/managed_observer_service.cpp
        src/observer_health.h
        src/observer_health.cpp
        src/chat_health.cpp
        src/chat_health.cpp
)


find_package(CURL REQUIRED)
find_package(OpenSSL REQUIRED COMPONENTS Crypto)
find_package(nlohmann_json CONFIG REQUIRED)

target_link_libraries(logos_observer_module_plugin
    PRIVATE
        CURL::libcurl
        OpenSSL::Crypto
        nlohmann_json::nlohmann_json
)
