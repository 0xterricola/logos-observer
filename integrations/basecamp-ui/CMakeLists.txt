cmake_minimum_required(VERSION 3.14)
project(LogosObserverUIPlugin LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(DEFINED ENV{LOGOS_MODULE_BUILDER_ROOT})
    include($ENV{LOGOS_MODULE_BUILDER_ROOT}/cmake/LogosModule.cmake)
else()
    message(FATAL_ERROR "LOGOS_MODULE_BUILDER_ROOT is not set")
endif()

logos_module(
    NAME logos_observer_ui
    REP_FILE src/ObserverManagerBackend.rep
    SOURCES
        src/ObserverManagerPluginInterface.h
        src/ObserverManagerPlugin.h
        src/ObserverManagerPlugin.cpp
        src/ObserverManagerBackend.h
        src/ObserverManagerBackend.cpp
        src/third_party/qrcodegen.cpp
)
