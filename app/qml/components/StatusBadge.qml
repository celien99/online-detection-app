import QtQuick
import styles

Rectangle {
    id: badge
    property string badgeText: "OK"
    property string badgeStatus: "ok"

    width: label.implicitWidth + 14
    height: 24
    radius: Theme.radiusSM
    color: {
        switch (badgeStatus) {
            case "ok": return Theme.statusOKDim;
            case "ng": return Theme.statusNGDim;
            case "warning": return Theme.statusWarningDim;
            default: return Qt.rgba(0.5, 0.5, 0.5, 0.2);
        }
    }
    border {
        width: 1
        color: {
            switch (badgeStatus) {
                case "ok": return Qt.rgba(0.247, 0.725, 0.314, 0.4);
                case "ng": return Qt.rgba(0.973, 0.318, 0.286, 0.4);
                case "warning": return Qt.rgba(0.824, 0.6, 0.114, 0.4);
                default: return Qt.rgba(0.5, 0.5, 0.5, 0.3);
            }
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
