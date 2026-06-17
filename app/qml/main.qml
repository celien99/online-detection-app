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
    property var reviewViewModel: null
    property var seatModelViewModel: null
    property var modelDeployViewModel: null
    property var diagnosticsViewModel: null

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
                text: qsTr("座椅缺陷在线检测系统")
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeMD
                font.bold: true
            }
            Rectangle {
                width: 1
                height: 24
                color: Theme.borderStrong
                Layout.leftMargin: Theme.spacingMD
                Layout.rightMargin: Theme.spacingMD
            }
            Text {
                text: qsTr("产线 ") + (window.mainViewModel ? window.mainViewModel.lineId : "--")
                color: Theme.accent
                font.pixelSize: Theme.fontSizeSM
            }

            Item {
                Layout.fillWidth: true
            }

            // Navigation tabs
            TabBar {
                id: navBar
                background: null
                Layout.preferredHeight: 48

                onCurrentIndexChanged: {
                    if (currentIndex === 1 && window.statsViewModel) {
                        window.statsViewModel.refresh();
                    }
                    if (currentIndex === 2 && window.logViewModel) {
                        window.logViewModel.refresh();
                    }
                    if (currentIndex === 3 && window.reviewViewModel) {
                        window.reviewViewModel.refresh();
                    }
                    if (currentIndex === 5 && window.seatModelViewModel) {
                        window.seatModelViewModel.refresh();
                    }
                    if (currentIndex === 6 && window.modelDeployViewModel) {
                        window.modelDeployViewModel.checkPlatformHealth();
                    }
                    if (currentIndex === 7 && window.diagnosticsViewModel) {
                        window.diagnosticsViewModel.refresh();
                    }
                }

                NavTabButton { text: qsTr("监控") }
                NavTabButton { text: qsTr("统计") }
                NavTabButton { text: qsTr("日志") }
                NavTabButton { text: qsTr("复核") }
                NavTabButton { text: qsTr("设置") }
                NavTabButton { text: qsTr("型号") }
                NavTabButton { text: qsTr("模型") }
                NavTabButton { text: qsTr("自检") }
            }
        }
    }

    // ── Content ──
    StackLayout {
        anchors.fill: parent
        currentIndex: navBar.currentIndex

        MainScreen {
            viewModel: window.mainViewModel
        }
        StatsScreen {
            total: window.statsViewModel ? window.statsViewModel.total : 0
            ok: window.statsViewModel ? window.statsViewModel.ok : 0
            ng: window.statsViewModel ? window.statsViewModel.ng : 0
            okRate: window.statsViewModel ? window.statsViewModel.okRate : 0.0
            viewModel: window.statsViewModel
        }
        LogScreen {
            logModel: window.logViewModel ? window.logViewModel.logs : []
            viewModel: window.logViewModel
        }
        ReviewScreen {
            reviewModel: window.reviewViewModel ? window.reviewViewModel.reviews : []
            viewModel: window.reviewViewModel
        }
        SettingsScreen {
            viewModel: window.settingsViewModel
        }
        SeatModelScreen {
            viewModel: window.seatModelViewModel
        }
        ModelDeployScreen {
            viewModel: window.modelDeployViewModel
        }
        DiagnosticsScreen {
            viewModel: window.diagnosticsViewModel
        }
    }
}
