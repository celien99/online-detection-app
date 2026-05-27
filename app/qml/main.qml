import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import "components"
import styles

ApplicationWindow {
    id: window
    visible: true
    title: qsTr("座椅缺陷在线检测系统")
    width: 1920
    height: 1080
    color: Theme.bgPrimary

    property var mainViewModel: null
    property var logViewModel: null
    property var statsViewModel: null
    property var settingsViewModel: null

    // ── Header ──
    header: Rectangle {
        height: 48
        color: Theme.bgSecondary

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Theme.spacingLG
            anchors.rightMargin: Theme.spacingSM
            spacing: 0

            // App title
            Text {
                text: qsTr("Seat Defect Inspector")
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeMD
                font.bold: true
            }
            Rectangle {
                width: 1; height: 24
                color: Theme.borderStrong
                Layout.leftMargin: Theme.spacingMD
                Layout.rightMargin: Theme.spacingMD
            }
            Text {
                text: qsTr("Line ") + (window.mainViewModel ? window.mainViewModel.lineId : "--")
                color: Theme.accent
                font.pixelSize: Theme.fontSizeSM
            }

            Item { Layout.fillWidth: true }

            // Navigation tabs
            TabBar {
                id: navBar
                background: null
                Layout.preferredHeight: 48

                onCurrentIndexChanged: {
                    if (currentIndex === 1 && window.statsViewModel) window.statsViewModel.refresh();
                    if (currentIndex === 2 && window.logViewModel) window.logViewModel.refresh();
                }

                TabButton {
                    id: monitorTab
                    text: qsTr("Monitor")
                    implicitHeight: 48
                    contentItem: Text {
                        text: monitorTab.text
                        color: monitorTab.checked ? Theme.accent : Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSM
                        font.bold: monitorTab.checked
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        color: "transparent"
                        Rectangle {
                            width: parent.width
                            height: 2
                            anchors.bottom: parent.bottom
                            color: monitorTab.checked ? Theme.accent : "transparent"
                        }
                    }
                }
                TabButton {
                    id: statsTab
                    text: qsTr("Statistics")
                    implicitHeight: 48
                    contentItem: Text {
                        text: statsTab.text
                        color: statsTab.checked ? Theme.accent : Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSM
                        font.bold: statsTab.checked
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        color: "transparent"
                        Rectangle {
                            width: parent.width
                            height: 2
                            anchors.bottom: parent.bottom
                            color: statsTab.checked ? Theme.accent : "transparent"
                        }
                    }
                }
                TabButton {
                    id: logTab
                    text: qsTr("Log")
                    implicitHeight: 48
                    contentItem: Text {
                        text: logTab.text
                        color: logTab.checked ? Theme.accent : Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSM
                        font.bold: logTab.checked
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        color: "transparent"
                        Rectangle {
                            width: parent.width
                            height: 2
                            anchors.bottom: parent.bottom
                            color: logTab.checked ? Theme.accent : "transparent"
                        }
                    }
                }
                TabButton {
                    id: settingsTab
                    text: qsTr("Settings")
                    implicitHeight: 48
                    contentItem: Text {
                        text: settingsTab.text
                        color: settingsTab.checked ? Theme.accent : Theme.textSecondary
                        font.pixelSize: Theme.fontSizeSM
                        font.bold: settingsTab.checked
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        color: "transparent"
                        Rectangle {
                            width: parent.width
                            height: 2
                            anchors.bottom: parent.bottom
                            color: settingsTab.checked ? Theme.accent : "transparent"
                        }
                    }
                }
            }
        }
    }

    // ── Content ──
    StackLayout {
        anchors.fill: parent
        currentIndex: navBar.currentIndex

        MainScreen { viewModel: window.mainViewModel }
        StatsScreen {
            total: window.statsViewModel ? window.statsViewModel.total : 0
            ok: window.statsViewModel ? window.statsViewModel.ok : 0
            ng: window.statsViewModel ? window.statsViewModel.ng : 0
            okRate: window.statsViewModel ? window.statsViewModel.okRate : 0.0
        }
        LogScreen { logModel: window.logViewModel ? window.logViewModel.logs : [] }
        SettingsScreen {}
    }
}
