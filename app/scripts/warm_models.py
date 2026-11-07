"""Build-time step: instantiate every model-backed scanner so weights are downloaded into
the image. At runtime the container sets HF_HUB_OFFLINE=1 and never touches the network
for models. Any download or load failure fails the image build, which is what we want.
"""

from gateway.layers.llmguard import LLMGuardInput, LLMGuardOutput
from gateway.layers.pii import PresidioRedactor

PresidioRedactor(("PERSON", "EMAIL_ADDRESS"))
LLMGuardInput(injection_threshold=0.9, toxicity_threshold=0.7)
LLMGuardOutput(toxicity_threshold=0.7)
print("models warmed")
