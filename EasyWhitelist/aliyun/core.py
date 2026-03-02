import logging
# from .sg import SecurityGroup
from .prefix import Prefix
# from ..util.nm import TEMPLATE_PREFIX


def aliyun_main(action, target, target_id, region, proxy=None) -> None:
    logging.info("enter aliyun...")
    pass


if __name__ == '__main__':

    # for i in range(1, 10):
    #     Prefix.create_prefix_list(PrefixListName=f'{TEMPLATE_PREFIX}{i}', Description=f'{TEMPLATE_PREFIX}{i}_desc')
    #     # Prefix.create_prefix_list()
    Prefix.associate_prefix_list("pl-bp1fa6b4ajysaelrsdnt", "cn-hangzhou")
