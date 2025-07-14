import os
import logging

logger = logging.getLogger(__name__)

def assert_output_file_does_not_exist(file_path: str) -> None:
    if os.path.exists(file_path):
        err_msg:str = f"El archivo de salida '{file_path}' ya existe."
        logger.info(err_msg)
        raise FileExistsError(err_msg)