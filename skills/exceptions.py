class SkillError(Exception): pass
class SkillInitializationError(SkillError): pass
class SkillExecutionError(SkillError): pass
class SkillValidationError(SkillError): pass
class SkillRegistrationError(SkillError): pass
class SkillUnavailableError(SkillError): pass
