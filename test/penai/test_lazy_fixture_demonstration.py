# Here we demonstrate a convenient pytest plugin called lazy fixture.
# It allows to use fixtures within test parametrization, which is especially useful
# if you want to test the method on different input data. Unfortunately, this forces one to use string
# interfaces for fixture but this is a price one might be willing to pay.
import pytest
from pytest_lazy_fixtures import lf


@pytest.mark.parametrize(
    "fixture, result",
    [
        (lf("fixture_1"), 1),
        (lf("fixture_2"), 2),
    ],
)
def test_demonstrateLazyFixture(fixture, result):
    assert fixture == result
