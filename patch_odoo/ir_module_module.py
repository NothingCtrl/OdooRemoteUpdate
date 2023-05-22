"""
This code to support remote update translation on Odoo from XMLRPC request
"""
from odoo import models

class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    def remote_update_translation(self, filter_lang: str = None):
        try:
            self.with_context(overwrite=self.env.context.get('overwrite'))._update_translations(filter_lang=filter_lang)
        except Exception as e:
            return {
                'status': False,
                'error': e.__str__()
            }
        return {"status": True, 'error': ''}
