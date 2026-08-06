/** Country metadata shared by phone entry and neighbouring-alert filters. */
export const PHONE_COUNTRIES = [
	{ code: 'BF', name: 'Burkina Faso', dial: '226' },
	{ code: 'CM', name: 'Cameroon', dial: '237' },
	{ code: 'TD', name: 'Chad', dial: '235' },
	{ code: 'ER', name: 'Eritrea', dial: '291' },
	{ code: 'ML', name: 'Mali', dial: '223' },
	{ code: 'MR', name: 'Mauritania', dial: '222' },
	{ code: 'NE', name: 'Niger', dial: '227' },
	{ code: 'NG', name: 'Nigeria', dial: '234' },
	{ code: 'RW', name: 'Rwanda', dial: '250' },
	{ code: 'SN', name: 'Senegal', dial: '221' },
	{ code: 'SD', name: 'Sudan', dial: '249' }
] as const;

export const NEIGHBOURING_COUNTRIES: Record<string, string[]> = {
	'Burkina Faso': ['Burkina Faso', 'Mali', 'Niger'],
	Cameroon: ['Cameroon', 'Nigeria', 'Chad'],
	Chad: ['Chad', 'Niger', 'Nigeria', 'Cameroon', 'Sudan'],
	Eritrea: ['Eritrea', 'Sudan'],
	Mali: ['Mali', 'Mauritania', 'Senegal', 'Burkina Faso', 'Niger'],
	Mauritania: ['Mauritania', 'Senegal', 'Mali'],
	Niger: ['Niger', 'Mali', 'Burkina Faso', 'Nigeria', 'Chad'],
	Nigeria: ['Nigeria', 'Niger', 'Chad', 'Cameroon'],
	Rwanda: ['Rwanda'],
	Senegal: ['Senegal', 'Mauritania', 'Mali'],
	Sudan: ['Sudan', 'Chad', 'Eritrea']
};

export function localToE164(localNumber: string, dial: string) {
	return `+${dial}${localNumber.replace(/\D/g, '').replace(/^0+/, '')}`;
}
