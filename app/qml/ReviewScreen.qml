import QtQuick
import QtQuick.Layouts
import styles

Rectangle {
    id: reviewScreen
    color: Theme.bgPrimary

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingLG
        spacing: Theme.spacingMD

        Text {
            text: qsTr("Review Queue")
            color: Theme.textPrimary
            font.pixelSize: Theme.fontSizeLG
            font.bold: true
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.bgCard
            radius: Theme.radiusMD
            border { width: 1; color: Theme.borderDefault }

            Column {
                anchors.centerIn: parent
                spacing: Theme.spacingSM
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: qsTr("No items pending review")
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontSizeMD
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: qsTr("Marked items from NGOverlay will appear here")
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontSizeSM
                }
            }
        }
    }
}
