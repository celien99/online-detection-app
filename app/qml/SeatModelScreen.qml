import QtQuick
import QtQuick.Layouts
import "components"
import styles

Rectangle {
    id: seatModelScreen
    color: Theme.bgPrimary

    property var viewModel: null

    ToastNotification {
        id: toast
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: Theme.spacingMD
        anchors.rightMargin: Theme.spacingMD
        z: 100
    }

    Connections {
        target: seatModelScreen.viewModel
        ignoreUnknownSignals: true
        function onToast(message, level) { toast.show(message, level); }
        function onRequestConfirmSwitch(modelId) { confirmDialog.modelId = modelId; confirmDialog.open(); }
    }

    IndustrialDialog {
        id: confirmDialog
        property string modelId: ""
        title: qsTr("切换座椅型号")
        acceptText: qsTr("确认切换")
        onAccepted: {
            if (seatModelScreen.viewModel && confirmDialog.modelId) {
                seatModelScreen.viewModel.confirmSwitch(confirmDialog.modelId);
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4
            Text {
                Layout.fillWidth: true
                text: qsTr("切换型号将重新加载检测引擎，当前检测任务会被中断。")
                color: Theme.textSecondary
                font.pixelSize: Theme.fontSizeSM
                wrapMode: Text.Wrap
                lineHeight: 1.6
            }
            Text {
                Layout.fillWidth: true
                text: qsTr("是否确认继续？")
                color: Theme.statusWarning
                font.pixelSize: Theme.fontSizeSM
                font.weight: Font.DemiBold
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingLG
        spacing: Theme.spacingMD

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: qsTr("座椅型号管理")
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeLG
                font.bold: true
            }
            Item { Layout.fillWidth: true }
            ActionButton {
                buttonText: qsTr("新增型号")
                bgColor: Theme.accentGreen
                textColor: "#000000"
                Layout.preferredWidth: 112
                implicitHeight: 36
                onClicked: addDialog.prepareAndOpen()
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ListView {
                id: modelList
                anchors.fill: parent
                model: seatModelScreen.viewModel ? seatModelScreen.viewModel.seatModels : []
                spacing: Theme.spacingSM
                visible: count > 0
                clip: true

                delegate: Rectangle {
                    width: ListView.view.width
                    implicitHeight: 80
                    color: Theme.cardGlass
                    radius: Theme.radiusMD
                    border { width: 1; color: modelData.is_default ? Theme.accentGreen : Theme.cardGlassBorder }

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.spacingMD
                        spacing: Theme.spacingMD

                        Rectangle {
                            width: 10; height: 10; radius: 5
                            color: modelData.is_default ? Theme.accentGreen : Theme.textMuted
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                text: modelData.display_name || modelData.id
                                color: Theme.textPrimary
                                font.pixelSize: Theme.fontSizeSM
                                font.bold: true
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                            Text {
                                text: modelData.description || ""
                                color: Theme.textSecondary
                                font.pixelSize: Theme.fontSizeXS
                                visible: text !== ""
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                            Text {
                                text: qsTr("关联相机: ") + (modelData.camera_ids ? modelData.camera_ids.join(", ") : qsTr("无"))
                                color: Theme.textMuted
                                font.pixelSize: Theme.fontSizeXS
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                        }

                        RowLayout {
                            spacing: Theme.spacingXS
                            ActionButton {
                                buttonText: qsTr("编辑")
                                bgColor: Theme.bgTertiary
                                implicitHeight: 28
                                implicitWidth: 52
                                font.pixelSize: Theme.fontSizeXS
                                onClicked: editDialog.prepareAndOpen(
                                    modelData.id,
                                    modelData.display_name || "",
                                    modelData.description || ""
                                )
                            }
                            ActionButton {
                                buttonText: modelData.is_default ? qsTr("默认") : qsTr("设为默认")
                                bgColor: modelData.is_default ? Theme.bgTertiary : Theme.accentGreen
                                textColor: modelData.is_default ? Theme.textMuted : "#000000"
                                implicitHeight: 28
                                implicitWidth: modelData.is_default ? 52 : 76
                                enabled: !modelData.is_default
                                font.pixelSize: Theme.fontSizeXS
                                onClicked: seatModelScreen.viewModel.setActive(modelData.id)
                            }
                            ActionButton {
                                buttonText: qsTr("删除")
                                bgColor: Qt.rgba(0.973, 0.318, 0.286, 0.16)
                                textColor: Theme.statusNG
                                implicitHeight: 28
                                implicitWidth: 52
                                font.pixelSize: Theme.fontSizeXS
                                onClicked: seatModelScreen.viewModel.deleteModel(modelData.id)
                            }
                        }
                    }
                }
            }

            EmptyState {
                anchors.fill: parent
                visible: modelList.count === 0
                title: qsTr("暂无座椅型号")
                message: qsTr("创建型号后，可以为不同座椅配置独立相机和检测模型。")
                badgeText: qsTr("MODEL")
                accentColor: Theme.accentGreen
            }
        }
    }

    IndustrialDialog {
        id: addDialog
        title: qsTr("新增座椅型号")
        acceptText: qsTr("创建")
        onAccepted: {
            seatModelScreen.viewModel.createModel(addIdInput.text, addNameInput.text, addDescInput.text);
        }

        function prepareAndOpen() {
            addIdInput.text = "";
            addNameInput.text = "";
            addDescInput.text = "";
            open();
            addIdInput.forceActiveFocus();
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8

            ColumnLayout {
                spacing: 4
                Layout.fillWidth: true
                Text {
                    text: qsTr("型号 ID")
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontSizeXS
                    font.weight: Font.Medium
                }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 40
                    color: addIdInput.activeFocus ? Qt.rgba(1, 1, 1, 0.06) : Theme.cardGlass
                    radius: Theme.radiusSM
                    border {
                        width: 1
                        color: addIdInput.activeFocus ? Theme.accent : Theme.cardGlassBorder
                    }
                    Behavior on border.color { ColorAnimation { duration: Theme.animFast } }

                    TextInput {
                        id: addIdInput
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        verticalAlignment: TextInput.AlignVCenter
                        color: Theme.textPrimary
                        font.pixelSize: Theme.fontSizeSM
                        activeFocusOnPress: true
                        selectByMouse: true
                        Text {
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            verticalAlignment: TextInput.AlignVCenter
                            text: "seat_model_001"
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontSizeSM
                            visible: !addIdInput.activeFocus && addIdInput.text === ""
                        }
                    }
                }
            }
            ColumnLayout {
                spacing: 4
                Layout.fillWidth: true
                Text {
                    text: qsTr("显示名称")
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontSizeXS
                    font.weight: Font.Medium
                }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 40
                    color: addNameInput.activeFocus ? Qt.rgba(1, 1, 1, 0.06) : Theme.cardGlass
                    radius: Theme.radiusSM
                    border {
                        width: 1
                        color: addNameInput.activeFocus ? Theme.accent : Theme.cardGlassBorder
                    }
                    Behavior on border.color { ColorAnimation { duration: Theme.animFast } }
                    TextInput {
                        id: addNameInput
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        verticalAlignment: TextInput.AlignVCenter
                        color: Theme.textPrimary
                        font.pixelSize: Theme.fontSizeSM
                        activeFocusOnPress: true
                        selectByMouse: true
                        Text {
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            verticalAlignment: TextInput.AlignVCenter
                            text: qsTr("座椅型号A")
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontSizeSM
                            visible: !addNameInput.activeFocus && addNameInput.text === ""
                        }
                    }
                }
            }
            ColumnLayout {
                spacing: 4
                Layout.fillWidth: true
                Text {
                    text: qsTr("描述")
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontSizeXS
                    font.weight: Font.Medium
                }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 40
                    color: addDescInput.activeFocus ? Qt.rgba(1, 1, 1, 0.06) : Theme.cardGlass
                    radius: Theme.radiusSM
                    border {
                        width: 1
                        color: addDescInput.activeFocus ? Theme.accent : Theme.cardGlassBorder
                    }
                    Behavior on border.color { ColorAnimation { duration: Theme.animFast } }
                    TextInput {
                        id: addDescInput
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        verticalAlignment: TextInput.AlignVCenter
                        color: Theme.textPrimary
                        font.pixelSize: Theme.fontSizeSM
                        activeFocusOnPress: true
                        selectByMouse: true
                        Text {
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            verticalAlignment: TextInput.AlignVCenter
                            text: qsTr("例如：M8 螺栓固定型，2024-03 起生产")
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontSizeSM
                            visible: !addDescInput.activeFocus && addDescInput.text === ""
                        }
                    }
                }
            }
        }
    }

    IndustrialDialog {
        id: editDialog
        property string modelId: ""
        title: qsTr("编辑型号")
        acceptText: qsTr("保存")
        onAccepted: {
            seatModelScreen.viewModel.updateModel(editDialog.modelId, editNameInput.text, editDescInput.text);
        }

        function prepareAndOpen(modelId, name, desc) {
            editDialog.modelId = modelId;
            editNameInput.text = name || "";
            editDescInput.text = desc || "";
            open();
            editNameInput.forceActiveFocus();
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8

            ColumnLayout {
                spacing: 4
                Layout.fillWidth: true
                Text {
                    text: qsTr("显示名称")
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontSizeXS
                    font.weight: Font.Medium
                }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 40
                    color: editNameInput.activeFocus ? Qt.rgba(1, 1, 1, 0.06) : Theme.cardGlass
                    radius: Theme.radiusSM
                    border {
                        width: 1
                        color: editNameInput.activeFocus ? Theme.accent : Theme.cardGlassBorder
                    }
                    Behavior on border.color { ColorAnimation { duration: Theme.animFast } }
                    TextInput {
                        id: editNameInput
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        verticalAlignment: TextInput.AlignVCenter
                        color: Theme.textPrimary
                        font.pixelSize: Theme.fontSizeSM
                        activeFocusOnPress: true
                        selectByMouse: true
                    }
                }
            }
            ColumnLayout {
                spacing: 4
                Layout.fillWidth: true
                Text {
                    text: qsTr("描述")
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontSizeXS
                    font.weight: Font.Medium
                }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 40
                    color: editDescInput.activeFocus ? Qt.rgba(1, 1, 1, 0.06) : Theme.cardGlass
                    radius: Theme.radiusSM
                    border {
                        width: 1
                        color: editDescInput.activeFocus ? Theme.accent : Theme.cardGlassBorder
                    }
                    Behavior on border.color { ColorAnimation { duration: Theme.animFast } }
                    TextInput {
                        id: editDescInput
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        verticalAlignment: TextInput.AlignVCenter
                        color: Theme.textPrimary
                        font.pixelSize: Theme.fontSizeSM
                        activeFocusOnPress: true
                        selectByMouse: true
                    }
                }
            }
        }
    }
}
