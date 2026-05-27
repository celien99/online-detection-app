import QtQuick

Rectangle {
    property string cardLabel: ""
    property string cardValue: ""
    property string cardSubtext: ""
    property color accentColor: Theme.accent

    color: Theme.bgCard
    radius: 4
    border { width: 1; color: Qt.rgba(0.5, 0.5, 0.5, 0.15) }

    implicitHeight: 70

    Column {
        anchors.fill: parent
        anchors.margins: 8
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
