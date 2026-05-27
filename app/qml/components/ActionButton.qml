import QtQuick
import QtQuick.Controls.Basic
import styles

Button {
    id: control
    property color bgColor: Theme.accent
    property color textColor: "#ffffff"
    property string buttonText: ""

    implicitHeight: Math.max(Theme.touchMin, implicitContentHeight + 20)

    font.pixelSize: Theme.fontSizeSM
    font.bold: true

    contentItem: Text {
        text: buttonText || control.text
        color: enabled ? textColor : Theme.textMuted
        font: control.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        radius: Theme.radiusMD
        color: control.pressed ? Qt.darker(bgColor, 1.15)
               : control.hovered ? Qt.lighter(bgColor, 1.08)
               : bgColor
        border {
            width: 1
            color: Qt.rgba(1, 1, 1, 0.08)
        }
    }
}
