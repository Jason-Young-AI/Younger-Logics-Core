import os
import ast
import glob

def get_source_segment(file_path, node):
    """
    获取AST节点对应的源代码片段

    Args:
        file_path: str, 源代码文件路径
        node: ast.AST, AST节点

    Returns:
        str: 节点对应的源代码
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    start_line, start_col = node.lineno - 1, node.col_offset
    end_line, end_col = node.end_lineno - 1, node.end_col_offset

    if start_line == end_line:
        return lines[start_line][start_col:end_col]
    else:
        # 获取多行代码
        code_lines = [lines[start_line][start_col:]]
        for i in range(start_line + 1, end_line):
            code_lines.append(lines[i].rstrip('\n'))
        code_lines.append(lines[end_line][:end_col])
        return '\n'.join(code_lines)

def find_nn_modules(repo_path):
    """
    在给定的git仓库路径中查找所有继承自torch.nn.Module的类
    
    Args:
        repo_path: str, git仓库的本地路径
        
    Returns:
        list: 包含所有nn.Module子类名称的列表
    """
    module_classes = []

    # 遍历仓库中所有的.py文件
    for py_file in glob.glob(os.path.join(repo_path, "**/*.py"), recursive=True):
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())
                
            # 跟踪torch.nn.Module的所有可能别名
            module_aliases = set()
            
            # 首先分析所有的导入语句
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        # 处理 import torch
                        if name.name == 'torch':
                            torch_name = name.asname if name.asname else 'torch'
                            module_aliases.add(f"{torch_name}.nn.Module")
                        # 处理 import torch.nn
                        elif name.name == 'torch.nn':
                            nn_name = name.asname if name.asname else 'torch.nn'
                            module_aliases.add(f"{nn_name}.Module")
                elif isinstance(node, ast.ImportFrom):
                    # 处理 from torch.nn import Module
                    # 处理 from torch.nn import *
                    if node.module == 'torch.nn':
                        for name in node.names:
                            if name.name == 'Module':
                                module_aliases.add(name.asname if name.asname else 'Module')
                            elif name.name == '*':
                                module_aliases.add('Module')
                    # 处理 from torch import nn
                    elif node.module == 'torch':
                        for name in node.names:
                            if name.name == 'nn':
                                nn_name = name.asname if name.asname else 'nn'
                                module_aliases.add(f"{nn_name}.Module")
            # 然后分析类定义
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # 检查类的基类
                    for base in node.bases:
                        base_name = None
                        # 处理 torch.nn.Module 形式
                        if isinstance(base, ast.Attribute):
                            if isinstance(base.value, ast.Attribute):
                                if isinstance(base.value.value, ast.Name):
                                    base_name = f"{base.value.value.id}.{base.value.attr}.{base.attr}"
                            else:
                                base_name = f"{base.value.id}.{base.attr}"
                        # 处理直接使用 Module 形式
                        elif isinstance(base, ast.Name):
                            base_name = base.id
                            
                        # 检查是否匹配任何已知的 Module 别名
                        if base_name in module_aliases:
                            # 获取类的完整源代码
                            module_classes.append([py_file,get_source_segment(py_file, node)])
                            break
                            
        except Exception as e:
            print(f"处理文件 {py_file} 时出错: {str(e)}")
            continue
            
    return module_classes

if __name__ == "__main__":
    repo_path = "test_cases/stable-diffusion"
    module_classes = find_nn_modules(repo_path)
    for module_class in module_classes:
        print(module_class[0])
        print(module_class[1])
