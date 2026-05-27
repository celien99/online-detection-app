import QtQuick
import styles

Rectangle {
    property string cardLabel: ""
    property string cardValue: ""
    property string cardSubtext: ""
    property color accentColor: Theme.accent

    color: Theme.bgCard
    radius: Theme.radiusMD
    border {
        width: 1
        color: Theme.borderDefault
    }

    implicitWidth: 160
    implicitHeight: 80

    Column {
        anchors.fill: parent
        anchors.margins: Theme.spacingMD
        spacing: 2

        Text {
            text: cardLabel
            font.pixelSize: Theme.fontSizeXS
            color: Theme.textSecondary
        }
        Text {
            text: cardValue
            font.pixelSize: Theme.fontSizeXL
            font.bold: true
            color: accentColor
        }
        Text {
            text: cardSubtext
            font.pixelSize: Theme.fontSizeXS
            color: Theme.textMuted
            visible: cardSubtext !== ""
        }
    }
}
