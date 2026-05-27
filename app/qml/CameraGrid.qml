import QtQuick

Item {
    id: grid

    property int columns: 2
    property int rows: 2
    property var cameraTiles: []

    Grid {
        anchors.fill: parent
        columns: grid.columns
        rows: grid.rows
        spacing: 2

        Repeater {
            model: grid.cameraTiles

            CameraTile {
                width: grid.width / grid.columns - 2
                height: grid.height / grid.rows - 2
                cameraId: modelData.cameraId || ""
                cameraStatus: modelData.status || "ok"
                defectLabel: modelData.defectLabel || ""
                live: modelData.live || false
            }
        }
    }
}
