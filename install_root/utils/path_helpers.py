import os


def repair_windows_path(path_str: str) -> str:
    """
    Repara rutas de Windows mal formadas.
    Ejemplo: 'C:UsersmariaAppDataLocalMovilidadESII' -> 'C:\\Users\\maria\\AppData\\Local\\MovilidadESII'
    """
    if not path_str:
        return ""

    if "\\" in path_str:
        return os.path.normpath(path_str)

    if "/" in path_str:
        return os.path.normpath(path_str.replace("/", "\\"))

    # C:Users... → C:\Users...
    if len(path_str) > 2 and path_str[1] == ":" and path_str[2] != "\\":
        path_str = path_str[0:2] + "\\" + path_str[2:]

    return os.path.normpath(path_str)
