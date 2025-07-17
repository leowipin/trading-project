import logging

def define_logging() -> None:
    logging.basicConfig(
        level = logging.INFO,
        format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("log2.txt"),
            logging.StreamHandler()
        ] 
    )