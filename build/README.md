# Build 目录

Build 目录用于存放生成的文件以及应用程序所需的资源文件。

目录结构如下：

* bin - 输出目录
* darwin - macOS 特定文件
* windows - Windows 特定文件

## Mac

`darwin` 目录包含特定于 Mac 构建的文件。
这些文件可以自定义并作为构建的一部分使用。要将这些文件恢复到默认状态，只需删除它们并使用 `wails build` 重新构建即可。

该目录包含以下文件：

- `Info.plist` - 用于 Mac 构建的主 plist 文件。在使用 `wails build` 构建时使用。
- `Info.dev.plist` - 与主 plist 文件相同，但在使用 `wails dev` 构建时使用。

## Windows

`windows` 目录包含在使用 `wails build` 构建时使用的清单 (manifest) 和资源 (rc) 文件。
这些文件可以根据您的应用程序进行自定义。要将这些文件恢复到默认状态，只需删除它们并使用 `wails build` 重新构建即可。

- `icon.ico` - 应用程序使用的图标。在使用 `wails build` 构建时使用。如果您希望使用不同的图标，只需将其替换为您自己的图标即可。如果该文件丢失，将使用 build 目录中的 `appicon.png` 文件创建一个新的 `icon.ico` 文件。
- `installer/*` - 用于创建 Windows 安装程序的文件。这些文件在使用 `wails build` 构建时使用。
- `info.json` - 用于 Windows 构建的应用程序详细信息。此处的数据将由 Windows 安装程序以及应用程序本身使用（右键单击 exe -> 属性 -> 详细信息）。
- `wails.exe.manifest` - 主应用程序清单文件。