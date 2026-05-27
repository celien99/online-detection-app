import QtQuick
import QtQuick.Controls.Basic

Button {
    id: control
    property color bgColor: Theme.accent
    property color textColor: "#ffffff"
    property string buttonText: ""

    implicitHeight: Math.max(48, implicitContentHeight + 16)
    font.pixelSize: Theme.fontSizeMD

    contentItem: Text {
        text: buttonText || control.text
        color: enabled ? textColor : Theme.textMuted
        font: control.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        radius: 6
        color: control.pressed ? Qt.darker(bgColor, 1.2)
               : control.hovered ? Qt.lighter(bgColor, 1.1)
               : bgColor
    }
}
