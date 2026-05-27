import QtQuick
import styles

Rectangle {
    id: badge
    property string badgeText: "OK"
    property string badgeStatus: "ok"

    width: label.implicitWidth + 12
    height: 22
    radius: 3
    color: {
        switch (badgeStatus) {
            case "ok": return Qt.rgba(0, 1, 0.53, 0.2);
            case "ng": return Qt.rgba(1, 0.27, 0.27, 0.2);
            case "warning": return Qt.rgba(1, 0.67, 0, 0.2);
            default: return Qt.rgba(0.5, 0.5, 0.5, 0.2);
        }
    }

    Text {
        id: label
        anchors.centerIn: parent
        text: badgeText
        font.pixelSize: Theme.fontSizeXS
        font.bold: true
        color: {
            switch (badgeStatus) {
                case "ok": return Theme.statusOK;
                case "ng": return Theme.statusNG;
                case "warning": return Theme.statusWarning;
                default: return Theme.textSecondary;
            }
        }
    }
}
