import QtQuick
import QtQuick.Layouts

GridLayout {
    id: grid

    property var cameraModel: []
    property string gridLayout: "2x2"

    columns: {
        var parts = gridLayout.split("x");
        return parts.length === 2 ? parseInt(parts[0]) : 2;
    }
    rows: {
        var parts = gridLayout.split("x");
        return parts.length === 2 ? parseInt(parts[1]) : 2;
    }
    rowSpacing: 4
    columnSpacing: 4

    Repeater {
        model: grid.cameraModel

        CameraTile {
            Layout.fillWidth: true
            Layout.fillHeight: true
            cameraId: modelData.cameraId || ""
            cameraStatus: modelData.status || "ok"
            defectLabel: modelData.defectLabel || ""
            live: modelData.live || false
        }
    }
}
