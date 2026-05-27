import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import "components"
import styles

Rectangle {
    id: statusBar
    property string lineId: ""
    property string systemStatus: "stopped"
    property int okCount: 0
    property int ngCount: 0
    property real tactRate: 0.0

    height: 52
    color: Theme.bgSecondary

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacingMD
        anchors.rightMargin: Theme.spacingMD
        spacing: Theme.spacingSM

        // Status indicator
        Rectangle {
            width: 14; height: 14; radius: 7
            color: {
                switch (systemStatus) {
                    case "running": return Theme.statusOK;
                    case "paused": return Theme.statusWarning;
                    default: return Theme.textMuted;
                }
            }
        }
        Text {
            text: {
                switch (systemStatus) {
                    case "running": return qsTr("Running");
                    case "paused": return qsTr("Paused");
                    default: return qsTr("Stopped");
                }
            }
            color: Theme.textPrimary
            font.pixelSize: Theme.fontSizeSM
            font.bold: true
            Layout.rightMargin: Theme.spacingMD
        }

        // Separator
        Rectangle { width: 1; height: 28; color: Theme.borderStrong }

        // Line info
        Text {
            text: qsTr("Line ") + lineId
            color: Theme.textSecondary
            font.pixelSize: Theme.fontSizeSM
            Layout.leftMargin: Theme.spacingMD
            Layout.rightMargin: Theme.spacingMD
            font.bold: true
        }

        // Separator
        Rectangle { width: 1; height: 28; color: Theme.borderStrong }

        // Tact rate
        Text {
            text: qsTr("Tact: ") + tactRate.toFixed(1) + "/min"
            color: Theme.textSecondary
            font.pixelSize: Theme.fontSizeSM
            Layout.leftMargin: Theme.spacingMD
            Layout.rightMargin: Theme.spacingMD
        }

        Rectangle { width: 1; height: 28; color: Theme.borderStrong }

        // OK count
        Text {
            text: qsTr("OK  ") + okCount
            color: Theme.statusOK
            font.pixelSize: Theme.fontSizeMD
            font.bold: true
            Layout.leftMargin: Theme.spacingMD
        }

        // NG count
        Text {
            text: qsTr("NG  ") + ngCount
            color: ngCount > 0 ? Theme.statusNG : Theme.textSecondary
            font.pixelSize: Theme.fontSizeMD
            font.bold: true
            Layout.leftMargin: Theme.spacingSM
        }

        Item { Layout.fillWidth: true }
    }
}
