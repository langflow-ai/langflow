from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output
from lfx_fastaf._base import FastAFBaseComponent, FastAFError, boolean_option, integer_option, require_text
from lfx_fastaf._inputs import (
    api_key_input,
    choice_input,
    localization_inputs,
    optional_bool,
    optional_int,
    query_input,
    text_input,
)


class FastAFAmazonComponent(FastAFBaseComponent):
    display_name = "FastAF Get Amazon Data"
    description = "Amazon search/product: 1 credit; offers/bestsellers: 5. Reviews are not offered."
    name = "FastAFAmazon"
    endpoint = "amazon"
    result_keys = ("results", "offers", "bestsellers")
    inputs = [
        api_key_input(),
        choice_input(
            "resource",
            "Resource",
            ["search", "product", "offers", "bestsellers"],
            "search",
            "Select one resource; parameters for other resources are omitted.",
            tool_mode=True,
        ),
        query_input(required=False),
        text_input(
            "asin", "ASIN", "Required for product/offers; the identifier after /dp/ in an Amazon URL.", tool_mode=True
        ),
        text_input("domain", "Amazon Domain Suffix", "com, co.uk, de, etc.; not a full hostname.", value="com"),
        *localization_inputs(),
        text_input(
            "postal_code",
            "Delivery Postal Code",
            "Localize availability/prices; not used for bestsellers.",
            advanced=True,
        ),
        optional_int("page", "Page", "1-100 for search; 1-2 for bestsellers; omitted for product/offers."),
        text_input(
            "category_id",
            "Bestseller Category",
            "Bestsellers only: slug/node from the category URL, e.g. kitchen/289668.",
            advanced=True,
        ),
        optional_bool(
            "full_list", "Full Bestseller List", "Bestsellers only; API default true combines the ranked list."
        ),
    ]
    outputs = [Output(display_name="Table", name="dataframe", method="fastaf_amazon")]

    def request_body(self) -> dict:
        resource = self.resource
        if resource not in {"search", "product", "offers", "bestsellers"}:
            msg = "Unsupported Amazon resource."
            raise FastAFError(msg)
        body = {"resource": resource, "domain": self.domain, "country": self.country}
        if resource != "offers":
            body["language"] = self.language
        if resource == "search":
            body["query"] = require_text(self.query, "Amazon Search Query")
        if resource in {"product", "offers"}:
            body["asin"] = require_text(self.asin, "ASIN")
        if resource != "bestsellers":
            body["postal_code"] = self.postal_code
        if resource in {"search", "bestsellers"}:
            body["page"] = integer_option(self.page, "Page", 1, 2 if resource == "bestsellers" else 100)
        if resource == "bestsellers":
            body.update(category_id=self.category_id, full_list=boolean_option(self.full_list))
        return body

    def fastaf_amazon(self) -> DataFrame:
        return DataFrame(self.fetch_content())
