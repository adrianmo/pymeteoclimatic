import pytest
from meteoclimatic import Station


class TestStation:

    _test_dict = {"name": "Reus - Nord (Tarragona)",
                  "code": "ESCAT4300000043206B",
                  "url": "http://www.meteoclimatic.net/perfil/ESCAT4300000043206B"}

    def test_init_ok(self):
        s = Station(**self._test_dict)
        assert s.name == "Reus - Nord (Tarragona)"
        assert s.code == "ESCAT4300000043206B"
        assert s.url == "http://www.meteoclimatic.net/perfil/ESCAT4300000043206B"

    @pytest.mark.parametrize("field_name,field_value,expected_error", [
        ("name", "", "Station name cannot be empty"),
        ("name", None, "Station name cannot be empty"),
        ("code", "", "Station code cannot be empty"),
        ("code", None, "Station code cannot be empty")
    ])
    def test_init_fails_when_wrong_data_provided(self, field_name, field_value, expected_error):
        d1 = self._test_dict.copy()
        d1[field_name] = field_value
        with pytest.raises(ValueError) as error:
            Station(**d1)
        assert str(error.value) == expected_error
