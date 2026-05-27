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

    footer: TabBar {
        id: navBar
        background: Rectangle { color: Theme.bgSecondary }
        onCurrentIndexChanged: {
            if (currentIndex === 1 && window.statsViewModel) window.statsViewModel.refresh();
            if (currentIndex === 2 && window.logViewModel) window.logViewModel.refresh();
        }

        TabButton {
            id: monitorTab
            text: qsTr("📷 监控")
            contentItem: Text { text: monitorTab.text; color: Theme.textPrimary; font.pixelSize: Theme.fontSizeSM }
            background: Rectangle { color: monitorTab.checked ? Theme.bgTertiary : "transparent" }
        }
        TabButton {
            id: statsTab
            text: qsTr("📊 统计")
            contentItem: Text { text: statsTab.text; color: Theme.textPrimary; font.pixelSize: Theme.fontSizeSM }
            background: Rectangle { color: statsTab.checked ? Theme.bgTertiary : "transparent" }
        }
        TabButton {
            id: logTab
            text: qsTr("📋 日志")
            contentItem: Text { text: logTab.text; color: Theme.textPrimary; font.pixelSize: Theme.fontSizeSM }
            background: Rectangle { color: logTab.checked ? Theme.bgTertiary : "transparent" }
        }
        TabButton {
            id: settingsTab
            text: qsTr("⚙ 设置")
            contentItem: Text { text: settingsTab.text; color: Theme.textPrimary; font.pixelSize: Theme.fontSizeSM }
            background: Rectangle { color: settingsTab.checked ? Theme.bgTertiary : "transparent" }
        }
    }

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
