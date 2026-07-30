from stackbox.config_gen.translator import DevStackTranslator


class TestDevStackTranslator:
    def test_translate_ironic_keys(self):
        translator = DevStackTranslator()
        localrc = {
            "IRONIC_ENABLED_HARDWARE_TYPES": "redfish",
            "IRONIC_ENABLED_BOOT_INTERFACES": "redfish-virtual-media",
            "IRONIC_AUTOMATED_CLEAN_ENABLED": "false",
        }
        result = translator.translate(localrc)

        assert "ironic" in result
        assert result["ironic"]["DEFAULT"]["enabled_hardware_types"] == "redfish"
        assert result["ironic"]["DEFAULT"]["enabled_boot_interfaces"] == "redfish-virtual-media"
        assert result["ironic"]["conductor"]["automated_clean"] == "false"

    def test_translate_neutron_ml2(self):
        translator = DevStackTranslator()
        localrc = {
            "Q_ML2_TENANT_NETWORK_TYPE": "vxlan",
            "Q_ML2_PLUGIN_MECHANISM_DRIVERS": "openvswitch",
        }
        result = translator.translate(localrc)

        assert "neutron_ml2" in result
        assert result["neutron_ml2"]["ml2"]["tenant_network_types"] == "vxlan"
        assert result["neutron_ml2"]["ml2"]["mechanism_drivers"] == "openvswitch"

    def test_none_mappings_are_skipped(self):
        translator = DevStackTranslator()
        localrc = {
            "IRONIC_VM_COUNT": "2",
            "DATABASE_PASSWORD": "secret",
        }
        result = translator.translate(localrc)
        assert result == {}

    def test_unmapped_keys(self):
        translator = DevStackTranslator()
        localrc = {
            "IRONIC_ENABLED_HARDWARE_TYPES": "redfish",
            "SOME_UNKNOWN_VAR": "value",
            "ANOTHER_UNKNOWN": "stuff",
        }
        unmapped = translator.unmapped_keys(localrc)
        assert unmapped == {"SOME_UNKNOWN_VAR", "ANOTHER_UNKNOWN"}

    def test_no_unmapped_keys_for_known_vars(self):
        translator = DevStackTranslator()
        localrc = {
            "IRONIC_ENABLED_HARDWARE_TYPES": "redfish",
            "DATABASE_PASSWORD": "secret",
            "IRONIC_VM_COUNT": "1",
        }
        assert translator.unmapped_keys(localrc) == set()

    def test_translate_from_fixture(self, vmedia_job_config):
        translator = DevStackTranslator()
        result = translator.translate(vmedia_job_config.devstack_localrc)
        assert "ironic" in result
        assert result["ironic"]["DEFAULT"]["enabled_hardware_types"] == "redfish"
