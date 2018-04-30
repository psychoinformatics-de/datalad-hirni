"""Rule set for specification of DICOM image series
"""

# TODO: should include series_is_valid()!

# define specification keywords of specification type 'dicomseries', that are
# subjects to the rule set
keywords = ['description', 'comment', 'subject', 'session', 'task', 'run',
            'modality', 'converter', 'id']


def series_is_valid(series):
    # filter "Series" entries from dataset metadata here, in order to get rid of
    # things, that aren't relevant image series
    # Those series are supposed to be ignored during conversion.
    # TODO: RF: integrate with rules definition

    # Note:
    # In 3T_visloc, SeriesNumber 0 is associated with ProtocolNames
    # 'DEFAULT PRESENTATION STATE' and 'ExamCard'.
    # All other SeriesNumbers have 1:1 relation to ProtocolNames and have 3-4
    # digits.
    # In 7T_ad there is no SeriesNumber 0 and the SeriesNumber doesn't have a 1:1
    # relation to ProtocolNames
    # Note: There also is a SeriesNumber 99 with protocol name 'Phoenix Document'?

    # Philips 3T Achieva
    if series['SeriesNumber'] == 0 and \
                    series['ProtocolName'] in ['DEFAULT PRESENTATION STATE',
                                               'ExamCard']:
        return False
    return True


def get_rules_from_metadata(dicommetadata):
    """Get the rules to apply

    Given a list of DICOM metadata dictionaries, determine which rule set to 
    apply (i.e. apply different rule set for different scanners).
    Note: This might need to change to the entire dict, datalad's dicom metadata 
    extractor delivers.

    Parameter:
    ----------
    dicommetadata: list of dict
        dicom metadata as extracted by datalad; one dict per image series

    Returns
    -------
    list of rule set classes
        wil be applied in order, therefore later ones overrule earlier ones
    """

    return [DefaultRules]


def apply_bids_label_restrictions(value):
    """
    Sanitize filenames for BIDS.
    """
    # only alphanumeric allowed
    # => remove everthing else

    if value is None:
        # Rules didn't find anything to apply, so don't put anything into the
        # spec.
        return None

    from six import string_types
    if not isinstance(value, string_types):
        value = str(value)

    import re
    pattern = re.compile('[\W_]+')  # check
    return pattern.sub('', value)


class DefaultRules(object):

    def __init__(self, dicommetadata):
        """
        
        Parameter
        ----------
        dicommetadata: list of dict
            dicom metadata as extracted by datalad; one dict per image series
        """
        self._dicoms = dicommetadata
        self.runs = dict()

    def __call__(self):
        spec_dicts = []
        for dicom_dict in self._dicoms:
            spec_dicts.append(self._rules(dicom_dict))
        return spec_dicts

    def _rules(self, record):

        protocol_name = record.get('ProtocolName', None)
        if protocol_name in self.runs:
            self.runs[protocol_name] += 1
        else:
            self.runs[protocol_name] = 1

        # TODO: Decide how to RF to apply custom rules. To be done within
        # datalad-neuroimaging, then just a custom one here.

        return {
                'description': record['SeriesDescription'],
                'comment': '',
                'subject': apply_bids_label_restrictions(_guess_subject(record)),
                'session': apply_bids_label_restrictions(protocol_name),
                'task': apply_bids_label_restrictions(_guess_task(record)),
                'run': self.runs[protocol_name],
                # TODO: BIDS-conform modality; (func, anat, dwi, fmap):
                'modality': apply_bids_label_restrictions(_guess_modality(record)),
                'data_type': apply_bids_label_restrictions(_guess_type(record)),
                'id': record.get('SeriesNumber', None),
                }


def _guess_subject(record):
    # Subject identification depends on scanner site:
    # Note: This possibly is overspecified ATM. Let's check out all
    #       scanners before being clear about how to safely distinguish
    #       them.
    if record.get("StationName") == "3T-PHILIPSMR" and \
            record.get(
                    "InstitutionName") == "Leibniz Institut Magdeburg" and \
            record.get("Manufacturer") == "Philips Medical Systems" and \
            record.get("ManufacturerModelName") == "Achieva dStream":

        subject = record.get("PatientName", None)
    elif record.get("StationName") == "AWP66017" and \
            record.get("InstitutionName") == "Neurologie" and \
            record.get("Manufacturer") == "SIEMENS" and \
            record.get("ManufacturerModelName") == "Prisma":

        subject = record.get("PatientID", None)
        if subject:
            subject = subject.split("_")[0]
    elif record.get("StationName") == "PCR7T1-15" and \
            record.get("InstitutionName") == "LIN" and \
            record.get("Manufacturer") == "SIEMENS" and \
            record.get("ManufacturerModelName") == "Investigational_Device_7T":

        subject = record.get("PatientID", None)
        if subject:
            subject = subject.split("_")[0]
    else:
        subject = record.get("PatientID", None)

    return subject


def _guess_task(record):

    protocol = record.get("ProtocolName", None)
    if protocol:
        prot_parts = protocol.lower().split('-') + protocol.lower().split('_')
        try:
            idx = prot_parts.index("task")
            task = prot_parts[idx + 1]
            return task
        except (ValueError, IndexError):
            # default to entire protocol name
            return protocol
    else:
        # default to entire protocol name
        return protocol


def _guess_modality(record):

    protocol = record.get("ProtocolName", None)
    if protocol:
        prot_parts = protocol.lower().split('-') + protocol.lower().split('_')

        # TODO: enhance (see BIDS spec)
        direct_search_terms = ["t1", "t1w", "t2", "t2w"]

        for m in direct_search_terms:
            if m in prot_parts:
                return m

    # found nothing, but modality isn't necessarily required
    return None


def _guess_type(record):
    # Note: Yarik uses such a mapping: should/could we too? (dbic_bids heuristic)
    # image_data_type = s.image_type[2]
    # image_type_seqtype = {
    #     'P': 'fmap',   # phase
    #     'FMRI': 'func',
    #     'MPR': 'anat',
    #     # 'M': 'func',  "magnitude"  -- can be for scout, anat, bold, fmap
    #     'DIFFUSION': 'dwi',
    #     'MIP_SAG': 'anat',  # angiography
    #     'MIP_COR': 'anat',  # angiography
    #     'MIP_TRA': 'anat',  # angiography
    # }.get(image_data_type, None)

    protocol = record.get("ProtocolName", None)
    if protocol:
        prot_parts = protocol.lower().split('-') + protocol.lower().split('_')

        direct_search_terms = ["func", "anat", "fmap", "dwi"]

        for m in direct_search_terms:
            if m in prot_parts:
                return m

    # no idea; default to 'func'
    return "func"



