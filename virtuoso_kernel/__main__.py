from ipykernel.kernelapp import IPKernelApp
from .kernel import VirtuosoKernel
IPKernelApp.launch_instance(kernel_class=VirtuosoKernel)
