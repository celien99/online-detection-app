import QtQuick
import QtQuick.Layouts
import styles

Rectangle {
    id: tile
    property string cameraId: ""
    property string cameraStatus: "ok"
    property string defectLabel: ""
    property bool live: false

    color: Theme.bgPrimary
    radius: Theme.radiusSM
    border {
        width: cameraStatus === "ng" ? 3 : 1
        color: cameraStatus === "ng" ? Theme.statusNG : Theme.borderDefault
    }

    // Camera feed
    Image {
        id: cameraImage
        anchors.fill: parent
        anchors.margins: 4
        source: "image://camera/" + cameraId
        cache: false
        fillMode: Image.PreserveAspectFit
    }

    // No signal placeholder
    Rectangle {
        anchors.centerIn: parent
        width: 120; height: 36; radius: Theme.radiusSM
        color: Qt.rgba(0, 0, 0, 0.5)
        visible: !live
        Text {
            anchors.centerIn: parent
            text: qsTr("No Signal")
            color: Theme.textMuted
            font.pixelSize: Theme.fontSizeSM
        }
    }

    // Bottom info bar
    Rectangle {
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 4
        height: 30
        radius: Theme.radiusSM
        color: Qt.rgba(0, 0, 0, 0.6)

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Theme.spacingSM
            anchors.rightMargin: Theme.spacingSM
            spacing: Theme.spacingSM

            // Live dot
            Rectangle {
                width: 8; height: 8; radius: 4
                Layout.alignment: Qt.AlignVCenter
                color: live ? Theme.statusOK : Theme.textMuted
            }

            Text {
                text: cameraId
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeXS
                font.bold: true
                Layout.alignment: Qt.AlignVCenter
                Layout.fillWidth: true
            }

            // NG badge in bottom bar
            Rectangle {
                visible: cameraStatus === "ng"
                Layout.alignment: Qt.AlignVCenter
                height: 20; radius: Theme.radiusSM
                width: ngBadgeText.implicitWidth + 12
                color: Theme.statusNGDim
                border { width: 1; color: Theme.statusNG }
                Text {
                    id: ngBadgeText
                    anchors.centerIn: parent
                    text: qsTr("NG")
                    color: Theme.statusNG
                    font.pixelSize: Theme.fontSizeXS
                    font.bold: true
                }
            }
        }
    }

    // Defect type floating label
    Rectangle {
        visible: cameraStatus === "ng" && defectLabel !== ""
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -24
        width: defectText.implicitWidth + 24
        height: 28
        radius: Theme.radiusSM
        color: Qt.rgba(0.973, 0.318, 0.286, 0.85)
        Text {
            id: defectText
            anchors.centerIn: parent
            text: defectLabel
            color: "#ffffff"
            font.pixelSize: Theme.fontSizeSM
            font.bold: true
        }
    }

    // NG border pulse animation
    SequentialAnimation on border.color {
        running: cameraStatus === "ng"
        loops: Animation.Infinite
        ColorAnimation { from: Theme.statusNG; to: Qt.rgba(0.973, 0.318, 0.286, 0.35); duration: 600 }
        ColorAnimation { from: Qt.rgba(0.973, 0.318, 0.286, 0.35); to: Theme.statusNG; duration: 600 }
    }
}
