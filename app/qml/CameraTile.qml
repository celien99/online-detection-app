import QtQuick
import styles

Rectangle {
    id: tile
    property string cameraId: ""
    property string cameraStatus: "ok"
    property string defectLabel: ""
    property bool live: false

    color: Theme.bgPrimary
    border {
        width: cameraStatus === "ng" ? 3 : 1
        color: {
            switch (cameraStatus) {
                case "ng": return Theme.statusNG;
                case "ok": return Qt.rgba(0.2, 0.2, 0.3, 1);
                default: return Theme.bgTertiary;
            }
        }
    }

    Image {
        id: cameraImage
        anchors.fill: parent
        anchors.margins: cameraStatus === "ng" ? 3 : 1
        source: "image://camera/" + cameraId
        cache: false
        fillMode: Image.PreserveAspectFit
    }

    Rectangle {
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        height: 28
        color: Qt.rgba(0, 0, 0, 0.55)

        Row {
            anchors.fill: parent
            anchors.margins: 4
            spacing: 8

            Rectangle {
                width: 8; height: 8; radius: 4
                anchors.verticalCenter: parent.verticalCenter
                color: live ? Theme.statusOK : Theme.textMuted
            }

            Text {
                text: cameraId
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeSM
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    Rectangle {
        visible: cameraStatus === "ng" && defectLabel !== ""
        anchors.centerIn: parent
        width: defectText.implicitWidth + 24
        height: 32
        radius: 4
        color: Qt.rgba(1, 0.27, 0.27, 0.8)

        Text {
            id: defectText
            anchors.centerIn: parent
            text: defectLabel
            color: "#ffffff"
            font.pixelSize: Theme.fontSizeSM
            font.bold: true
        }
    }

    SequentialAnimation on border.color {
        running: cameraStatus === "ng"
        loops: Animation.Infinite
        ColorAnimation { from: Theme.statusNG; to: Qt.rgba(1, 0.27, 0.27, 0.3); duration: 500 }
        ColorAnimation { from: Qt.rgba(1, 0.27, 0.27, 0.3); to: Theme.statusNG; duration: 500 }
    }
}
