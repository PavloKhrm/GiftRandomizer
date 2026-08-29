from .create_flow import setup as s3
from .menu import setup as s2
from .my_channels import setup as s5
from .my_giveaways import setup as s4
from .participation import setup as s6
from .start import setup as s1


def register_handlers(dp):
    s1(dp)
    s2(dp)
    s3(dp)
    s4(dp)
    s5(dp)
    s6(dp)
