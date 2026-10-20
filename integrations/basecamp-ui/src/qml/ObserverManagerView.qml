import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    implicitWidth: 900
    implicitHeight: 620
    color: "#0b0d10"

    readonly property var backend:
        logos ? logos.module("logos_observer_ui") : null

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 32
        spacing: 20

        Label {
            text: "Logos Observer"
            font.pixelSize: 28
            font.bold: true
            color: "#ffffff"
        }

        Label {
            text: "Service monitoring and configuration"
            color: "#9ca3af"
            font.pixelSize: 14
        }

        GroupBox {
            title: "Observer Connection"
            label: Label {
                text: "Observer Connection"
                color: "#e2e8f0"
                font.pixelSize: 15
                font.bold: true
            }
            Layout.fillWidth: true

            ColumnLayout {
                anchors.fill: parent
                spacing: 12

                Label {
                    text: "Observer HTTPS Health URL"
                    color: "#cbd5e1"
                }

                TextField {
                    id: endpointField
                    implicitHeight: 42
                    color: "#f8fafc"
                    placeholderTextColor: "#94a3b8"
                    selectionColor: "#256f7c"
                    selectedTextColor: "#ffffff"
                    background: Rectangle {
                        color: "#1e293b"
                        radius: 6
                        border.color: "#475569"
                    }
                    Layout.fillWidth: true
                    placeholderText: "https://192.168.x.x:8444/health"
                }

                Label {
                    text: "Trusted TLS Certificate Path"
                    color: "#cbd5e1"
                }

                TextField {
                    id: certField
                    implicitHeight: 42
                    color: "#f8fafc"
                    placeholderTextColor: "#94a3b8"
                    selectionColor: "#256f7c"
                    selectedTextColor: "#ffffff"
                    background: Rectangle {
                        color: "#1e293b"
                        radius: 6
                        border.color: "#475569"
                    }
                    Layout.fillWidth: true
                    placeholderText: "/path/to/observer-v2-cert.pem"
                }

                Label {
                    text: "Observer SPKI Pin"
                    color: "#cbd5e1"
                }

                TextField {
                    id: pinField
                    implicitHeight: 42
                    color: "#f8fafc"
                    placeholderTextColor: "#94a3b8"
                    selectionColor: "#256f7c"
                    selectedTextColor: "#ffffff"
                    background: Rectangle {
                        color: "#1e293b"
                        radius: 6
                        border.color: "#475569"
                    }
                    Layout.fillWidth: true
                    placeholderText: "sha256/..."
                }

                Button {
                    id: healthButton

                    implicitHeight: 42
                    leftPadding: 20
                    rightPadding: 20

                    contentItem: Text {
                        text: healthButton.text
                        color: healthButton.enabled ? "#08141c" : "#94a3b8"
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    background: Rectangle {
                        color: healthButton.enabled ? "#67dbe6" : "#293444"
                        radius: 6
                    }

                    text: root.backend && root.backend.healthBusy
                          ? "Checking..."
                          : "Check Health"

                    enabled: !!root.backend
                             && root.backend.ready
                             && !root.backend.healthBusy
                             && endpointField.text.trim().length > 0
                             && certField.text.trim().length > 0
                             && pinField.text.trim().length > 0

                    onClicked: {
                        root.backend.checkHealth(
                            endpointField.text.trim(),
                            certField.text.trim(),
                            pinField.text.trim()
                        )
                    }
                }
            }
        }

        GroupBox {
            title: "Service Health"
            label: Label {
                text: "Service Health"
                color: "#e2e8f0"
                font.pixelSize: 15
                font.bold: true
            }
            Layout.fillWidth: true
            Layout.fillHeight: true

            ColumnLayout {
                anchors.fill: parent
                spacing: 12

                Label {
                    text: root.backend
                          ? root.backend.healthStatus
                          : "Backend unavailable"

                    font.pixelSize: 18
                    font.bold: true
                    color: "#e2e8f0"
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 16

                    Label {
                        text: "Chat bridge: " + (root.backend
                            ? root.backend.chatBridgeStatus
                            : "Unknown")
                        color: "#cbd5e1"
                        Layout.fillWidth: true
                    }

                    Label {
                        text: "Basecamp Chat: " + (root.backend
                            ? root.backend.chatStatus
                            : "Unknown")
                        color: "#cbd5e1"
                        Layout.fillWidth: true
                    }

                    Button {
                        text: root.backend && root.backend.chatBusy
                            ? "Checking..."
                            : "Check Chat"
                        enabled: !!root.backend
                            && root.backend.ready
                            && !root.backend.chatBusy
                        onClicked: root.backend.checkChatHealth()
                    }
                }

                Label {
                    Layout.fillWidth: true
                    text: "Conversations: " + (root.backend
                        ? root.backend.conversationsStatus
                        : "Unknown")
                    color: "#cbd5e1"
                    font.pixelSize: 14
                }

                Label {
                    Layout.fillWidth: true
                    text: root.backend ? root.backend.chatDetails : ""
                    color: "#94a3b8"
                    font.pixelSize: 12
                    wrapMode: Text.Wrap
                }

                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    TextArea {
                        text: root.backend
                              ? root.backend.healthDetails
                              : ""

                        readOnly: true
                        color: "#cbd5e1"
                        font.pixelSize: 14
                        background: Rectangle {
                            color: "#161f2c"
                            radius: 6
                        }
                        wrapMode: TextArea.Wrap
                        selectByMouse: true
                    }
                }
            }
        }
    }
}
