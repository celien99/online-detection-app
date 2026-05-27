import QtQuick
import QtQuick.Controls.Basic
import "components"

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

        TabButton {
            text: qsTr("📷 监控")
            contentItem: Text { text: parent.text; color: Theme.textPrimary; font.pixelSize: Theme.fontSizeSM }
            background: Rectangle { color: parent.checked ? Theme.bgTertiary : "transparent" }
        }
        TabButton {
            text: qsTr("📊 统计")
            contentItem: Text { text: parent.text; color: Theme.textPrimary; font.pixelSize: Theme.fontSizeSM }
            background: Rectangle { color: parent.checked ? Theme.bgTertiary : "transparent" }
        }
        TabButton {
            text: qsTr("📋 日志")
            contentItem: Text { text: parent.text; color: Theme.textPrimary; font.pixelSize: Theme.fontSizeSM }
            background: Rectangle { color: parent.checked ? Theme.bgTertiary : "transparent" }
        }
        TabButton {
            text: qsTr("⚙ 设置")
            contentItem: Text { text: parent.text; color: Theme.textPrimary; font.pixelSize: Theme.fontSizeSM }
            background: Rectangle { color: parent.checked ? Theme.bgTertiary : "transparent" }
        }
    }

    StackView {
        id: stackView
        anchors.fill: parent
        initialItem: MainScreen { viewModel: window.mainViewModel }

        onCurrentIndexChanged: {
            if (currentIndex === 1) window.statsViewModel.refresh();
            if (currentIndex === 2) window.logViewModel.refresh();
        }
    }
}
