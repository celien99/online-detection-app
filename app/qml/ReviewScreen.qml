import QtQuick
import styles

Rectangle {
    id: reviewScreen
    color: Theme.bgPrimary

    Text {
        anchors.centerIn: parent
        text: qsTr("🔍 复核队列 — 待实现")
        color: Theme.textMuted
        font.pixelSize: Theme.fontSizeMD
    }
}
