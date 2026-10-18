"""Portable gateway adapters; importing this package never makes a network call."""
from . import model, resources

catalog = resources.catalog
run = resources.run
activate = resources.activate
configure = model.configure
public_config = model.public_config

__all__ = ['catalog', 'run', 'activate', 'configure', 'public_config', 'model', 'resources']
