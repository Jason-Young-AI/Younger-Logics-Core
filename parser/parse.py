import os
import ast
import glob
import astroid
from astroid import MANAGER
import json
import importlib
import sys

class ClassInfo:
    def __init__(self, class_name, parent_classes=[], children_classes=[], code=""):
        self.class_name = class_name
        self.parent_classes = parent_classes
        self.children_classes = children_classes
        self.code = code

    def convert_to_dict(self):
        return {
            "class_name": self.class_name,
            "parent_classes": self.parent_classes,
            "children_classes": self.children_classes,
            "code": self.code,
        }


class Class_Inheritance_Graph:
    def __init__(self, repo_path):
        self.repo_path = repo_path
        self.class_info_dict = self.build_class_inheritance_graph(repo_path)
        self.nn_moudles_subclass = self.find_nn_modules(self.class_info_dict)

    def convert_to_dict(self):
        return {
            "class_info_dict": {
                class_name: class_info.convert_to_dict()
                for class_name, class_info in self.class_info_dict.items()
            },
            "nn_moudles_subclass": {
                class_name: class_info.convert_to_dict()
                for class_name, class_info in self.nn_moudles_subclass.items()
            },
        }

    def get_module_qname(self, module_name, current_file_path, repo_path):
        """
        获取模块的完整限定名

        Args:
            module_name: str, 模块名称
            current_file_path: str, 当前文件路径
            repo_path: str, 仓库根路径
            node_level: int, 当前节点的层级
        Returns:
            str: 模块的完整限定名
        """
        # 检查是否为标准库或已安装的第三方库
        try:
            if module_name != "":
                importlib.import_module(module_name.split(".")[0])
            else:
                raise ImportError
            return module_name
        except ImportError:
            # 如果不是外部库，说明是本地模块
            # 根据node_level，找到当前文件的相对路径
            rel_path = os.path.relpath(os.path.dirname(current_file_path), repo_path)
            if rel_path == ".":
                return module_name
            elif module_name == "":
                return rel_path
            else:
                return f"{rel_path.replace(os.sep, '.')}.{module_name}"
        except Exception as e:
            print(f"获取模块的完整限定名时出错: {str(e)}")
            return module_name

    def get_source_segment(self, file_path, node):
        """
        获取AST节点对应的源代码片段

        Args:
            file_path: str, 源代码文件路径
            node: ast.AST, AST节点

        Returns:
            str: 节点对应的源代码
        """
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        start_line, start_col = node.lineno - 1, node.col_offset
        end_line, end_col = node.end_lineno - 1, node.end_col_offset

        if start_line == end_line:
            return lines[start_line][start_col:end_col]
        else:
            # 获取多行代码
            code_lines = [lines[start_line][start_col:]]
            for i in range(start_line + 1, end_line):
                code_lines.append(lines[i].rstrip("\n"))
            code_lines.append(lines[end_line][:end_col])
            return "\n".join(code_lines)

    def convert_qname_to_class_name(self, qname, repo_path):
        # 获得current_file_path
        current_file_path = os.path.abspath(__file__)
        # 将repo_path转换为绝对路径
        repo_path = os.path.abspath(repo_path)
        # 计算repo_path相对于current_file_path的路径
        rel_path = os.path.relpath(repo_path, os.path.dirname(current_file_path))
        # 将rel_path以os.sep为分隔符切割
        rel_path_parts = rel_path.split(os.sep)
        # 将qname以.为分隔符切割
        qname_parts = qname.split(".")
        # qname_parts中的前几个元素就是rel_path_parts，移除这几个元素
        flag = True
        for i in range(len(rel_path_parts)):
            if qname_parts[i] != rel_path_parts[i]:
                flag = False
                break
        if flag:
            qname_parts = qname_parts[len(rel_path_parts) :]
        # 将qname_parts重新拼接为字符串
        return ".".join(qname_parts)

    def build_class_inheritance_graph(self, repo_path):
        class_info_dict: dict[str, ClassInfo] = {}
        # 遍历repo_path下的所有py文件
        for py_file in glob.glob(os.path.join(repo_path, "**/*.py"), recursive=True):
            try:
                # 解析代码
                module = MANAGER.ast_from_file(py_file)
                short_class_name_to_qname = {}
                # 收集导入信息
                for node in module.nodes_of_class(astroid.ImportFrom):
                    # 对于import from ... import ... 的语句，modname为空
                    # 对这种情况进行特殊处理：找到有多少个.
                    module_name = node.modname
                    current_file_path = py_file
                    if node.level is not None:
                        for _ in range(node.level - 1):
                            current_file_path = os.path.dirname(current_file_path)

                    full_module_name = self.get_module_qname(
                        module_name, current_file_path, repo_path
                    )
                    for name, alias in node.names:
                        imported_name = alias or name
                        short_class_name_to_qname[imported_name] = (
                            f"{full_module_name}.{name}"
                            if full_module_name != ""
                            else name
                        )
                for node in module.nodes_of_class(astroid.Import):
                    for name, alias in node.names:
                        imported_name = alias or name.split(".")[-1]
                        full_module_name = self.get_module_qname(
                            name, py_file, repo_path
                        )
                        short_class_name_to_qname[imported_name] = full_module_name

                # 遍历module中的所有类
                for node in module.nodes_of_class(astroid.ClassDef):
                    # 创建ClassInfo对象
                    # class_name要求完整名称
                    class_name = node.qname()
                    # 用convert_qname_to_class_name函数将class_name转换为完整名称
                    class_name = self.convert_qname_to_class_name(class_name, repo_path)
                    # 找到node的直接父类，用base来做
                    parent_classes = []
                    for base in node.bases:
                        try:
                            # 使用infer来获得base的完整名称
                            base_class_name = base.inferred()[0].qname()
                            base_class_name = self.convert_qname_to_class_name(
                                base_class_name, repo_path
                            )
                        except Exception as e:
                            base_class_name = base.as_string()
                            for short_class_name in short_class_name_to_qname:
                                if base_class_name.startswith(short_class_name):
                                    # 将base_class_name中的class_name替换为class_name_to_qname[class_name]
                                    base_class_name = (
                                        short_class_name_to_qname[short_class_name]
                                        + base_class_name[len(short_class_name) :]
                                    )
                                    break
                        parent_classes.append(base_class_name)

                    # 创建ClassInfo对象
                    class_info = ClassInfo(
                        class_name,
                        parent_classes,
                        [],
                        self.get_source_segment(py_file, node),
                    )
                    # 建立一个字典，key为class_name，value为class_info
                    class_info_dict[class_name] = class_info
            except Exception as e:
                print(f"处理文件 {py_file} 时出错: {str(e)}")
                continue
        # 找到每个ClassInfo的children_classes
        for class_name, class_info in class_info_dict.items():
            for parent_class in class_info.parent_classes:
                if parent_class in class_info_dict:
                    class_info_dict[parent_class].children_classes.append(class_name)

        return class_info_dict

    def find_nn_modules(self, class_info_dict: dict[str, ClassInfo]):
        # 此时class_info_dict中已经包含了所有类的继承关系
        nn_moudles_subclass = {}
        # 使用bfs的方法，找到所有is_nn_modules为True的类
        for class_name, class_info in class_info_dict.items():
            flag = False
            for parent_class in class_info.parent_classes:
                if parent_class in [
                    "torch.nn.Module",
                    "torch.nn.modules.module.Module",
                ]:
                    flag = True
                    break
            if flag:
                # 使用bfs的方法，找到所有is_nn_modules为True的类
                nn_moudles_subclass[class_name] = class_info
                queue = [class_name]
                while queue:
                    current_class_name = queue.pop(0)
                    for child_class_name in class_info_dict[
                        current_class_name
                    ].children_classes:
                        if child_class_name not in nn_moudles_subclass:
                            queue.append(child_class_name)
                            nn_moudles_subclass[child_class_name] = class_info_dict[
                                child_class_name
                            ]
        return nn_moudles_subclass


if __name__ == "__main__":
    import time
    if len(sys.argv) == 1:
        repo_path = "test_cases/resnet"
        save_path = "module_info.json"
    elif len(sys.argv) == 2:
        repo_path = sys.argv[1]
        save_path = "module_info.json"
    else:
        repo_path = sys.argv[1]
        save_path = sys.argv[2]
    t0 = time.time()
    class_inheritance_graph = Class_Inheritance_Graph(repo_path)
    # nn_moudles_subclass = class_inheritance_graph.nn_moudles_subclass
    module_info_json = json.dumps(class_inheritance_graph.convert_to_dict(), indent=4)
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(module_info_json)

    class_info_dict = class_inheritance_graph.class_info_dict
    nn_moudles_subclass = class_inheritance_graph.nn_moudles_subclass
    # for class_name, class_info in nn_moudles_subclass.items():
    #     print(class_name)
    #     print(class_info.parent_classes)
