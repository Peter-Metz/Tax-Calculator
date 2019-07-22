import numpy as np
import taxcalc as tc


class Calculator(tc.Calculator):
    """
    Customized Calculator class that inherits all tc.Calculator data and
    methods, adding or overriding some to get the desired customization.
    """

    def __init__(self, policy=None, records=None, verbose=False,
                 sync_years=True, consumption=None,
                 # customization argument
                 ptax_em_active=False):
        # call the parent class constructor
        super().__init__(policy=policy, records=records,
                         verbose=verbose, sync_years=sync_years,
                         consumption=consumption)
        
        self.ptax_em_active = ptax_em_active
        # declare ptax_em_param dictionary that will contain pseudo ptax exemption policy
        self.ptax_em_param = dict()

    def specify_pseudo_ptax_policy(self):
        # reform implementation year
        reform_year = 2019
        # specify dictionary of parameter names and values for reform_year
        self.ptax_em_param = {
            # exemption amount
            'FICA_ss_em': 5000,
            # apply exemption to employer portion of FICA (exemption automatically applied to employee portion)
            'FICA_ss_em_employer': True
        }
        # set pseudo ptax parameter values for current year
        this_year = self.current_year
        if self.ptax_em_active and this_year >= reform_year:
            # set inflation-indexed values of ptax_em for this year
            irates = self.__policy.inflation_rates()
            syr = tc.Policy.JSON_START_YEAR

            value = self.ptax_em_param['FICA_ss_em']
            for year in range(reform_year, this_year):
                value *= (1.0 + irates[year - syr])
            self.ptax_em_param['FICA_ss_em'] = np.round(
                value, 2)  # to nearest penny
        else:  # if policy not active or if this year is before the reform year
            # set ceiling to zero
            self.ptax_em_param['FICA_ss_em'] = 0

    def pseudo_ptax_amount(self):
        
        pol = self.__policy
        recs = self.__records

        ptax_em = self.ptax_em_param['FICA_ss_em']
        fica_em_employer = self.ptax_em_param['FICA_ss_em_employer']

        # compute sey and its individual components
        sey_p = recs.e00900p + recs.e02100p + recs.k1bx14p
        sey_s = recs.e00900s + recs.e02100s + recs.k1bx14s

        # sey adjusted for exemption
        sey_p_em = np.where(sey_p > ptax_em, sey_p - ptax_em, 0)
        sey_s_em = np.where(sey_s > ptax_em, sey_s - ptax_em, 0)

        # gross wage and salary pre-exemption
        gross_was_p = recs.e00200p + recs.pencon_p
        gross_was_s = recs.e00200s + recs.pencon_s

        # wage and salary adjusted for exemption
        gross_was_p_em = np.where(
            gross_was_p > ptax_em, gross_was_p - ptax_em, 0)
        gross_was_s_em = np.where(
            gross_was_s > ptax_em, gross_was_s - ptax_em, 0)

        # pre-exemption taxable earnings for OASDI FICA
        txearn_was_p = np.where(
            pol.SS_Earnings_c < gross_was_p, pol.SS_Earnings_c, gross_was_p)
        txearn_was_s = np.where(
            pol.SS_Earnings_c < gross_was_s, pol.SS_Earnings_c, gross_was_s)

        # post-exemption taxable earnings for OASDI FICA
        txearn_was_p_em = np.where(pol.SS_Earnings_c < gross_was_p_em,
                                   pol.SS_Earnings_c, gross_was_p_em)
        txearn_was_s_em = np.where(pol.SS_Earnings_c < gross_was_s_em,
                                   pol.SS_Earnings_c, gross_was_s_em)

        #fraction of se income subject to FICA tax
        sey_frac = 1.0 - 0.5 * (pol.FICA_ss_trt + pol.FICA_mc_trt)

        # pre-exemption taxable self-employment income for OASDI SECA
        temp1_p = np.where(0. > sey_p * sey_frac, 0, sey_p * sey_frac)
        temp2_p = pol.SS_Earnings_c - txearn_was_p
        txearn_sey_p = np.where(temp1_p > temp2_p, temp2_p, temp1_p)

        temp1_s = np.where(0. > sey_s * sey_frac, 0, sey_s * sey_frac)
        temp2_s = pol.SS_Earnings_c - txearn_was_s
        txearn_sey_s = np.where(temp1_s > temp2_s, temp2_s, temp1_s)

        # post-exemption taxable self-employment income for OASDI SECA
        temp1_p_em = np.where(0. > sey_p_em * sey_frac, 0, sey_p_em * sey_frac)
        temp2_p_em = pol.SS_Earnings_c - txearn_was_p_em
        txearn_sey_p_em = np.where(
            temp1_p_em > temp2_p_em, temp2_p_em, temp1_p_em)

        temp1_s_em = np.where(0. > sey_s_em * sey_frac, 0, sey_s_em * sey_frac)
        temp2_s_em = pol.SS_Earnings_c - txearn_was_s_em
        txearn_sey_s_em = np.where(
            temp1_s_em > temp2_s_em, temp2_s_em, temp1_s_em)

        # calculate employee portion of FICA using post-exemption taxable
        # earnings
        ptax_ss_was_p_employee = pol.FICA_ss_trt * 0.5 * txearn_was_p_em
        ptax_ss_was_s_employee = pol.FICA_ss_trt * 0.5 * txearn_was_s_em
        setax_ss_p_employee = pol.FICA_ss_trt * 0.5 * txearn_sey_p_em
        setax_ss_s_employee = pol.FICA_ss_trt * 0.5 * txearn_sey_s_em

        # if exemption applies to employer portion of FICA,
        # use post-exemption taxable earnings for exmployer calculation
        if fica_em_employer:
            ptax_ss_was_p_employer = pol.FICA_ss_trt * 0.5 * txearn_was_p_em
            ptax_ss_was_s_employer = pol.FICA_ss_trt * 0.5 * txearn_was_s_em
            setax_ss_p_employer = pol.FICA_ss_trt * 0.5 * txearn_sey_p_em
            setax_ss_s_employer = pol.FICA_ss_trt * 0.5 * txearn_sey_s_em

        # otherwise, use pre-exemption taxable earnings
        else:
            ptax_ss_was_p_employer = pol.FICA_ss_trt * 0.5 * txearn_was_p
            ptax_ss_was_s_employer = pol.FICA_ss_trt * 0.5 * txearn_was_s
            setax_ss_p_employer = pol.FICA_ss_trt * 0.5 * txearn_sey_p
            setax_ss_s_employer = pol.FICA_ss_trt * 0.5 * txearn_sey_s

        # post-exemption OASDI payroll taxes
        ptax_ss_was_p = ptax_ss_was_p_employee + ptax_ss_was_p_employer
        ptax_ss_was_s = ptax_ss_was_s_employee + ptax_ss_was_s_employer
        setax_ss_p = setax_ss_p_employee + setax_ss_p_employer
        setax_ss_s = setax_ss_s_employee + setax_ss_s_employer

        recs.ptax_oasdi = ptax_ss_was_p + ptax_ss_was_s + setax_ss_p + setax_ss_s

    def calc_all(self, zero_out_calc_vars=False):
        """
        Call all tax-calculation functions for the current_year.
        """
        tc.BenefitPrograms(self)
        self._calc_one_year(zero_out_calc_vars)
        tc.BenefitSurtax(self)
        tc.BenefitLimitation(self)
        tc.FairShareTax(self.__policy, self.__records)
        tc.LumpSumTax(self.__policy, self.__records)
        # specify new method to set pseudo ptax policy parameters
        self.specify_pseudo_ptax_policy()  # (see above)
        # call new method to calculate pseudo ptax amount
        self.pseudo_ptax_amount()  # (see above)
        tc.ExpandIncome(self.__policy, self.__records)
        tc.AfterTaxIncome(self.__policy, self.__records)

pol = tc.Policy()  # baseline policy is current-law policy

puf_path = '/Users/petermetz/Tax-Calculator/puf.csv'
recs = tc.Records(puf_path)

calc1 = Calculator(policy=pol, records=recs, ptax_em_active=False)
calc2 = Calculator(policy=pol, records=recs, ptax_em_active=True)

# calculate tax liabilities for years around the reform year
cyr_first = 2019
cyr_last = 2028
for cyr in range(cyr_first, cyr_last + 1):
    # advance to and calculate for specified cyr
    calc1.advance_to_year(cyr)
    calc1.calc_all()
    calc2.advance_to_year(cyr)
    calc2.calc_all()
    # tabulate weighted amounts
    funits = calc1.total_weight()
    ptax_oasdi1 = calc1.weighted_total('ptax_oasdi')
    ptax_oasdi2 = calc2.weighted_total('ptax_oasdi')
    diff = ptax_oasdi1 - ptax_oasdi2
    # print weighted amounts for cyr
    if cyr == cyr_first:
        print('YEAR  UNITS   PTAX1   PTAX2  DIFF')
    line = '{}  {:.1f}  {:5.1f}  {:5.1f}  {:5.1f}'
    print(line.format(cyr, funits * 1e-6,
                      ptax_oasdi1 * 1e-9, ptax_oasdi2 * 1e-9, diff * 1e-9))
