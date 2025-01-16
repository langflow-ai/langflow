import pytest

from langflow.components.langchain_utilities.keybert_link_extractor import KeybertLinkExtractorComponent
from langflow.schema import Data
from langflow.services.cache.utils import CacheMiss

from langchain_community.graph_vectorstores.links import Link
from langchain_core.documents import Document

from tests.base import ComponentTestBaseWithClient

from loguru import logger

@pytest.mark.usefixtures("client")
class TestKeybertLinkExtractorComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return KeybertLinkExtractorComponent

    @pytest.fixture
    def default_kwargs(self, test_text):
        return {
            "_session_id": "123",
            "extract_keywords_kwargs": {},
            "data_input": test_text
        }
        
    @pytest.fixture
    def file_names_mapping(self):
        return [      
            {"version": "1.0.19", "module": "langchain_utilities", "file_name": "gliner_link_extractor"},
            {"version": "1.1.0", "module": "langchain_utilities", "file_name": "gliner_link_extractor"},
            {"version": "1.1.1", "module": "langchain_utilities", "file_name": "gliner_link_extractor"},
        ]
        
    @pytest.fixture
    def test_text(self):
        text = """
        The life of Alexander the Great, one of the most renowned military leaders in history, is a tale of ambition, conquest, and cultural integration. Born in 356 BCE in Pella, the capital of Macedonia, Alexander was the son of King Philip II and Queen Olympias. He was tutored by the philosopher Aristotle, who instilled in him a love for learning and culture.

        Early Life and Education
        Alexander III of Macedon, later known as Alexander the Great, was born on July 20, 356 BCE, in Pella, the capital of Macedonia. His father, King Philip II, united most of the Greek city-states under Macedonian rule. His mother, Queen Olympias, claimed descent from Achilles. Educated by the philosopher Aristotle from age 13 to 16, Alexander studied subjects such as philosophy, politics, and science, developing a lifelong appreciation for knowledge and culture.

        In 340 BCE, at age 16, Alexander acted as regent while Philip campaigned and demonstrated his military aptitude by suppressing a rebellion and founding a city, Alexandropolis.

        Ascension to Power
        When Philip II was assassinated in 336 BCE, Alexander ascended to the throne at age 20. He quickly consolidated power by eliminating rivals and securing loyalty from the Greek city-states, reaffirming Macedonian hegemony through a campaign against Thebes in 335 BCE, which he destroyed as a warning to others.

        Military Campaigns and Conquests
        Conquest of the Persian Empire (334–330 BCE):

        334 BCE: Alexander crossed the Hellespont into Asia Minor and defeated the Persians at the Battle of Granicus.
        333 BCE: At the Battle of Issus, he routed the forces of Darius III, capturing Darius’s family.
        332 BCE: After a lengthy siege, Alexander took Tyre, and in Egypt, he was hailed as a liberator and declared the son of the god Amun. He founded Alexandria, the first of many cities bearing his name.
        331 BCE: In the decisive Battle of Gaugamela, Alexander defeated Darius III and effectively took control of the Persian Empire.
        Expansion into Central Asia and India (329–325 BCE):

        Alexander pursued Darius III, who was ultimately killed by his own men in 330 BCE. Alexander executed Darius's murderers and declared himself "King of Asia".
        In 327 BCE, he invaded the Indian subcontinent, winning the Battle of Hydaspes River against King Porus in 326 BCE. Despite the victory, his troops refused to march further east, prompting their return.
        Return to Babylon and Death (324–323 BCE):

        On the way back, Alexander endured grueling campaigns in the Gedrosian Desert (present-day Iran). He attempted to consolidate his empire, promoting unity between Macedonians and Persians through marriages and governance reforms.
        Alexander died in Babylon on June 10 or 11, 323 BCE, under mysterious circumstances, possibly fever, poisoning, or malaria.
        Cultural Integration and Legacy
        Alexander sought to merge Greek and local cultures, a process known as Hellenization, which left a lasting impact on regions spanning Greece, Egypt, Persia, and India. He founded over 20 cities, such as Alexandria in Egypt, which became a major center of learning and commerce. His policies included adopting local customs and appointing non-Macedonians to administrative roles.

        Associations and Mythology
        Alexander was deified by many cultures during and after his reign. In Islamic tradition, he is often associated with "Iskandar Dhul-Qarnayn" (Alexander the Two-Horned) and linked to legends such as the building of the iron wall against Gog and Magog.
        His death spurred the fragmentation of his empire among his generals, the Diadochi, who divided it into the Ptolemaic, Seleucid, and Antigonid kingdoms.
        Tomb and Mysteries
        Alexander's burial site remains a mystery. Historical sources suggest it was in Alexandria, Egypt, but the exact location is unknown. His sarcophagus and associated treasures have been sought by archaeologists and explorers for centuries​

        Alexander’s conquests reshaped the ancient world, blending cultures and setting the stage for the Hellenistic period, marked by advancements in art, science, and philosophy
        """
        
        paragraphs = text.strip().split('\n\n')
        documents = [Document(page_content=paragraph) for paragraph in paragraphs if paragraph]
        return documents
  
    @pytest.fixture
    def all_tags(self):
        return [
            'aristotle', 'philosopher', 'macedonia', 'alexander', 'philip', 'aristotle',
            'macedonian', 'macedonia', 'alexander', 'philip', 'alexandropolis',
            'founding', 'regent', 'alexander', 'philip', 'macedonian', 'ascended',
            'assassinated', 'alexander', 'philip', 'conquest', 'bce', 'persian',
            'conquests', 'empire', 'alexandria', 'persians', 'persian', 'darius',
            'alexander', 'babylon', 'hydaspes', 'king', 'darius', 'alexander',
            'alexandria', 'macedonians', 'persians', 'alexander', 'persia',
            'archaeologists', 'alexandria', 'alexander', 'sarcophagus', 'iskandar',
            'cultures', 'hellenistic', 'ancient', 'conquests', 'alexander'
        ]
        
    def test_link_extraction(self, component_class, default_kwargs, all_tags):
        component = component_class(**default_kwargs)
        assert isinstance(component, KeybertLinkExtractorComponent)
        data = component.transform_data()
        assert data is not None
        assert len(data) == 10
        for datum in data:
            assert isinstance(datum, Data)
            links = datum.data['links']
            assert links is not None
            for link in links:
                assert isinstance(link, Link)
                assert link.tag in all_tags

    def test_post_code_processing(self, component_class, default_kwargs):
        """
        Test the post-processing of code in the component class.
        This test verifies that the component class correctly processes the code 
        and converts it to a frontend node with the expected structure and values.
        Args:
            component_class (class): The class of the component to be tested.
            default_kwargs (dict): The default keyword arguments to initialize the component.
        Asserts:
            - The node data is not None.
            - The 'value' of 'labels' in the 'template' of node data is "people, places, dates, events".
            - The string "alexander" is present in the 'page_content' of the first item in 'data_input' of 'template'.
        """
        
        component = component_class(**default_kwargs)
        frontend_node = component.to_frontend_node()
        node_data = frontend_node["data"]["node"]
        assert node_data is not None
        assert "alexander" in node_data["template"]["data_input"]["value"][0]["page_content"].lower()

    def test_model_caching(self, test_text):
        """
        Test the model caching in the KeybertLinkExtractorComponent.
        This test verifies that the model is cached and loaded correctly.
        Asserts:
            - The model is loaded and cached.
            - The model is loaded from cache.
        """
        
        component = KeybertLinkExtractorComponent(
            _session_id="123",
            kind="keyword",
            extract_keywords_kwargs={},
            data_input=test_text
        )
        
        model = component._shared_component_cache.get("kw_model")
        assert isinstance(model, CacheMiss)
        assert component.load_model() is not None
        
        another_component = KeybertLinkExtractorComponent(
            _session_id="123",
            kind="keyword",
            extract_keywords_kwargs={},
            data_input=test_text
        )
        
        model = component._shared_component_cache.get("kw_model")
        assert not isinstance(model, CacheMiss)
