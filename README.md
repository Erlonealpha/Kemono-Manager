# 简易的Kemono(Coomer)管理/下载器 Manager/Downloader
### 能做什么 What it can do
- 批量添加并下载Kemono/Coomer用户附件 Batch add 和 download Kemono/Coomer user attachments
- 高度自定义的文件链接，将所有源文件集中存储并使用硬链接实现自定义的文件管理 Highly customizable file links, centrally store all source files 和 use hard links to achieve custom file management
### 示例用法 How to use
这只是其中一种用法，将来还会推出WebUI和flutter-KemonoViewer
使用[command] -h查看帮助 Use[Command] -h see help info
```shell
python .\main_cli.py -h
python .\main_cli.py add-user -h
```
- 添加User数据到数据库 Add User data to database.
```shell
python .\main_cli.py add-user -url https://kemono.su/fanbox/user/233333
python .\main_cli.py add-user -user_id 233333 -service fanbox
python .\main_cli.py add-user -server_id 23333333333
python .\main_cli.py add-users -urls https://kemono.su/fanbox/user/233333,https://kemono.su/fanbox/user/233334
```
- 下载指定User的附件 Download user's attachments.
```shell
python .\main_cli.py download [-user_id xxx -service xxx | -url xxx| -server_id xxx] -filter [path/filter.py | attachment.post_id == "xxxx"] -root path/Resource -tmp path/tmp
python .\main_cli.py download-multi -urls xxxx,xxxx -filter xxxx
```
- 生成用于硬链接的文件信息 Generate files info for hardlink.
```shell
$folder_expr = \
base_dir = path_join(creator.public_name, creator.service) \
if attachment.type == "cover": \
        folder = "cover" \
    elif attachment.type == "thumbnail": \
        folder = "thumbnail" \
    else: \
        folder = get_folder_by_filetype(file_type) \
return path_join(base_dir, folder) 

$file_expr = \
f, ext = path_splitext(attachment.name) \
return by_alpha_condition(f, post.title) + ext

python .\main_cli.py gen-files -url xxx -root path/KemonoFiles -folder_expr [path/folder_expr.py | $folder_expr] -file_expr [path/file_expr.py | $file_expr]
python .\main_cli.py gen-files-multi -urls xxx
```
- 硬链接文件 Hardlink files
```shell
python .\main_cli.py hardlink -url xxx -root path/Resource
python .\main_cli.py hardlink-multi -urls xxx -root path/Resource
```
### 示例的文件结构 Example of the folder structure
```
KemonoManager/
│
├── KemonoResource/
│   ├── 00/
│   │   ├── 00/
│   │   │   └── 00...
│   │   └── ...
│   ├── ...
│   └── tmp/
└── KemonoFiles
    ├── author1/
    │   ├── service/
    │   │   ├── compress/
    │   │   │   ├── content
    │   │   ├── covers/
    │   │   │   ├── content
    │   │   │   └── ...
    │   │   ├── thumnails/
    │   │   │   ├── content
    │   │   │   └── ...
    │   │   ├── images/  
    │   │   │   ├── content
    │   │   │   └── ...
    │   │   └── images_01/
    │   │       └── ...
    │   │   └── .../
    │   │       └── ...
    │   └── service2/  
    │       └── ...
    └── author2/
        ├── service/
        └── service2/               

```
### 使用代理池 Use ProxyPool
在以下文件夹中添加示例代理池数据 Create proxy pool data file in below directory.

data/proxies/

示例 example_proxies.json
```json
[
    {
        "http": "http://127.0.0.1:42000",
        "https": "https://127.0.0.1:42000",
        "name": "🇷🇺 俄罗斯01-IEPL专线",
        "area": "欧洲",
        "country": "俄罗斯",
        "host": "127.0.0.1",
        "port": 42000
    },
    {
        "http": "http://127.0.0.1:42001",
        "https": "https://127.0.0.1:42001",
        "name": "🇨🇦 加拿大01-IEPL专线",
        "area": "北美洲",
        "country": "加拿大",
        "host": "127.0.0.1",
        "port": 42001
    }
]
```
### 更多功能介绍 More features introduction
